#!/usr/bin/env python3
"""Isolated Church membership snapshot bootstrap + annual scheduled refresh.

Daily temple attendance script never calls this module.  All prospective annual
snapshots are parsed and validated in memory before any file changes.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
SNAPSHOTS = ROOT / 'membership_data'
REPORTS = ROOT / 'membership_update_reports'
HISTORY_ROOT = 'https://raw.githubusercontent.com/acbass49/scrape_lds_stats/refs/heads/main/data/'
COUNTRY_NAV = 'https://news-uk.churchofjesuschrist.org/facts-and-statistics/country/brazil'
COUNTRY_PREFIX = 'https://newsroom.churchofjesuschrist.org/facts-and-statistics/country/'
STATE_PREFIX = 'https://news-uk.churchofjesuschrist.org/facts-and-statistics/state/'
WORLD_URL = 'https://www.churchofjesuschrist.org/learn/facts-statistics?lang=eng'
FIELDS = ['scope', 'name', 'members', 'source_url']
STATE_NAMES = (
    'Alabama Alaska Arizona Arkansas California Colorado Connecticut Delaware Florida '
    'Georgia Hawaii Idaho Illinois Indiana Iowa Kansas Kentucky Louisiana Maine Maryland '
    'Massachusetts Michigan Minnesota Mississippi Missouri Montana Nebraska Nevada '
    'New_Hampshire New_Jersey New_Mexico New_York North_Carolina North_Dakota Ohio '
    'Oklahoma Oregon Pennsylvania Rhode_Island South_Carolina South_Dakota Tennessee '
    'Texas Utah Vermont Virginia Washington West_Virginia Wisconsin Wyoming'
).split()
STATE_NAMES = tuple(name.replace('_', ' ') for name in STATE_NAMES)
ALIASES = {'Cote d’Ivoire': 'Ivory Coast', "Cote d'Ivoire": 'Ivory Coast', 'Côte d’Ivoire': 'Ivory Coast',
           "Côte d'Ivoire": 'Ivory Coast', 'Cabo Verde': 'Cape Verde', 'Eswatini': 'Swaziland',
           'Korea': 'South Korea'}
HISTORY_FILES = {2024: 'country-2025-04-27.csv', 2025: 'country-2026-04-16.csv'}
MIN_COUNTRIES = 140  # guard against a partial directory or unexpectedly truncated source

class ValidationError(RuntimeError):
    pass

def get(url: str) -> str:
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=(12, 35), headers={'User-Agent':'ChurchStatsMembershipResearch/2.0 (annual statistics research)'})
            response.raise_for_status()
            if len(response.content) < 150:
                raise ValueError('Response unexpectedly short')
            return response.text
        except (requests.RequestException, ValueError):
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise AssertionError('unreachable')

def norm(name: str) -> str:
    name = unicodedata.normalize('NFC', name.strip().replace('\u00a0', ' '))
    return ALIASES.get(name, name)

def read_csv(path: Path) -> dict[tuple[str,str],dict]:
    with path.open(encoding='utf-8-sig',newline='') as f:
        data = {}
        for line, row in enumerate(csv.DictReader(f), 2):
            key = (row['scope'].strip(),norm(row['name']))
            if key in data:
                raise ValidationError(f'{path} duplicate key {key} at line {line}')
            count = int(row['members'])
            if count <= 0:
                raise ValidationError(f'{path} nonpositive count for {key}')
            data[key] = dict(scope=key[0],name=key[1],members=count,source_url=row['source_url'])
    return data

def csv_bytes(rows: dict) -> bytes:
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream,fieldnames=FIELDS,lineterminator='\n')
    writer.writeheader()
    for key in sorted(rows):
        writer.writerow(rows[key])
    return stream.getvalue().encode('utf-8')

def write_snapshot_atomic(path: Path, rows: dict) -> None:
    # No output path written until candidate passes all validation.
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_bytes(csv_bytes(rows))
    temp.replace(path)

def read_historical(year: int) -> dict:
    url = HISTORY_ROOT + HISTORY_FILES[year]
    values = {}
    for row in csv.DictReader(io.StringIO(get(url))):
        name = norm(row['Name'])
        if name == 'United States':
            continue  # the US denominator is the sum of the 50 states
        try:
            count = int(row['TotalChurchMembership'].replace(',',''))
        except (ValueError, KeyError):
            continue
        if count <= 0:  # 0 in historical source often means not disclosed
            continue
        key=('country',name)
        if key in values:
            raise ValidationError(f'Duplicate historical name in {url}: {name}')
        values[key]=dict(scope='country',name=name,members=count,source_url=url)
    if len(values) < MIN_COUNTRIES:
        raise ValidationError(f'Historical {year} dataset has only {len(values)} positive country counts')
    return values

def validate_snapshot(rows: dict, year: int) -> None:
    missing_states={('state',n) for n in STATE_NAMES}-rows.keys()
    if missing_states:
        raise ValidationError(f'{year} missing states: {sorted(missing_states)}')
    us=sum(rows[('state',n)]['members'] for n in STATE_NAMES)
    if not 4_000_000 <= us <= 10_000_000:
        raise ValidationError(f'{year} US sum implausible: {us:,}')
    if any(rows[('state',n)]['members'] > 3_000_000 for n in STATE_NAMES):
        raise ValidationError(f'{year} individual state count implausible')
    world=rows.get(('world','Worldwide'),{}).get('members',0)
    if not 10_000_000 <= world <= 30_000_000:
        raise ValidationError(f'{year} worldwide count implausible: {world:,}')
    country_count=sum(k[0]=='country' for k in rows)
    if country_count < MIN_COUNTRIES:
        raise ValidationError(f'{year} only {country_count} countries; minimum {MIN_COUNTRIES}')
    for k, row in rows.items():
        if not isinstance(row['members'],int) or row['members'] <= 0 or not row['source_url'].startswith('https://'):
            raise ValidationError(f'{year} malformed row {k}')

def bootstrap(directory: Path = SNAPSHOTS) -> dict:
    """Expand 2024/25 using published historical archives, preserving verified rows.

    Preserves the original 50-state figures, existing 44-country data, and
    official worldwide totals. Never overwrites an annual snapshot for >=2026.
    """
    current={y: read_csv(directory/f'{y}.csv') for y in (2024,2025)}
    archives={y:read_historical(y) for y in (2024,2025)}
    # Preserve every positive published count, even if a geography appears
    # in only one baseline year. The model needs TWO annual anchors to publish
    # its rate and will safely omit an unsupported denominator in the interim.
    for year in (2024,2025):
        for key, archived_row in archives[year].items():
            if key not in current[year]:
                current[year][key]=archived_row
        validate_snapshot(current[year],year)
    for year in (2024,2025):
        write_snapshot_atomic(directory/f'{year}.csv',current[year])
    return {'status':'bootstrapped','countries_2024':sum(k[0]=='country' for k in current[2024]),
            'countries_2025':sum(k[0]=='country' for k in current[2025]),
            'not_public_in_both_years':sorted(k[1] for k in (set(archives[2024]) ^ set(archives[2025])))}

def second_monday(year: int) -> date:
    april1=date(year,4,1)
    return april1 + timedelta(days=(0-april1.weekday())%7+7)

def retry_day(today: date) -> int | None:
    offset=(today-second_monday(today.year)).days
    return offset if 0<=offset<=6 else None

def _lines(html: str) -> str:
    soup=BeautifulSoup(html,'html.parser')
    for node in soup(['script','style','noscript']):
        node.decompose()
    return re.sub(r'\s+',' ',soup.get_text(' ',strip=True).replace('\xa0',' '))

def published_year(text: str) -> int | None:
    m=re.search(r'Last\s+Updated\s+On\s+(?:31\s+Dec(?:ember)?|Dec(?:ember)?\s+31)\s*,?\s*(20\d{2})\b',text,re.I)
    return int(m.group(1)) if m else None

def membership_from_html(html: str, *, kind: str, expected_year: int | None=None) -> int:
    soup=BeautifulSoup(html,'html.parser')
    # Legacy site sometimes has large site-wide worldwide membership widgets.
    # Restrict parsing to the main geographical section, never the worldwide widget.
    raw=_lines(html)
    segment=re.split(r'\bWorldwide\s+Statistics\b',raw,flags=re.I)[0]
    if expected_year is not None:
        actual=published_year(segment)
        if actual != expected_year:
            raise ValidationError(f'Page reporting year {actual}, expected {expected_year}')
    if kind=='legacy':
        m=re.search(r'(?<!\d)([\d,]+)\s+Total\s+Church\s+Membership\b',segment,re.I)
        if not m:
            m=re.search(r'\bChurch\s+Membership\b\s+([\d,]+)',segment,re.I)
    elif kind=='world':
        m=re.search(r'Total\s+Church\s+Membership\s+([\d,]+)',segment,re.I)
        if not m:
            m=re.search(r'([\d,]+)\s+Total\s+Church\s+Membership',segment,re.I)
    else:  # modern location page: heading 'Church Membership', then number
        m=re.search(r'\bChurch\s+Membership\s+([\d,]+)',segment,re.I)
    if not m:
        raise ValidationError(f'Membership not found in {kind} page')
    count=int(m.group(1).replace(',',''))
    if count <= 0:
        raise ValidationError(f'No positive published membership (value {count})')
    return count

def discover_country_pages() -> dict[str,str]:
    html=get(COUNTRY_NAV)
    soup=BeautifulSoup(html,'html.parser')
    links={}
    for a in soup.find_all('a',href=True):
        path=urlparse(urljoin(COUNTRY_NAV,a['href'])).path
        m=re.fullmatch(r'/facts-and-statistics/country/([a-z0-9-]+)',path)
        if not m:
            continue
        name=norm(' '.join(a.get_text(' ',strip=True).split()))
        if not name or name.lower() in ('countries','country'):
            continue
        url=COUNTRY_PREFIX + m.group(1)
        if name in links and links[name] != url:
            raise ValidationError(f'Conflicting country slug for {name}')
        links[name]=url
    if len(links)<MIN_COUNTRIES:
        raise ValidationError(f'Official country directory contains {len(links)} links; expected >= {MIN_COUNTRIES}')
    return links

def fetch_country(item: tuple[str,str], year: int):
    name,url=item
    html=get(url)
    return ('country',name), dict(scope='country',name=name,
        members=membership_from_html(html,kind='modern',expected_year=year),source_url=url)

def fetch_state(name: str):
    slug=name.lower().replace(' ','-')
    url=STATE_PREFIX+slug
    html=get(url)
    return ('state',name), dict(scope='state',name=name,
        members=membership_from_html(html,kind='legacy'),source_url=url)

def validate_candidate(candidate: dict, previous: dict, year: int, discovered: dict, us_country: int | None):
    validate_snapshot(candidate,year)
    errors=[]
    old_countries={k for k in previous if k[0]=='country'}
    missing_countries=old_countries-candidate.keys()
    if missing_countries:
        errors.append(f'Previously published countries missing: {sorted(missing_countries)}')
    if len(discovered)<MIN_COUNTRIES:
        errors.append('Geography discovery incomplete')
    # A new year cannot be a disguised scrape of last year's stale pages.
    states_changed=sum(candidate[('state',n)]['members']!=previous[('state',n)]['members'] for n in STATE_NAMES)
    shared_countries=[k for k in old_countries if k in candidate]
    countries_changed=sum(candidate[k]['members']!=previous[k]['members'] for k in shared_countries)
    if states_changed < 15:
        errors.append(f'Only {states_changed}/50 states changed; likely previous-year data')
    if countries_changed < max(40, int(.3*len(shared_countries))):
        errors.append(f'Only {countries_changed}/{len(shared_countries)} countries changed; likely previous-year data')
    old_us=sum(previous[('state',n)]['members'] for n in STATE_NAMES)
    new_us=sum(candidate[('state',n)]['members'] for n in STATE_NAMES)
    if abs(new_us/old_us-1) > .05:
        errors.append(f'US total changed >5%: {old_us:,} -> {new_us:,}')
    old_world=previous[('world','Worldwide')]['members']
    new_world=candidate[('world','Worldwide')]['members']
    if abs(new_world/old_world-1) > .08:
        errors.append(f'Worldwide total changed >8%: {old_world:,} -> {new_world:,}')
    for k,row in candidate.items():
        old=previous.get(k)
        if old is None:
            continue
        prior=old['members']; current=row['members']
        if k[0]=='state' and abs(current/prior-1)>.15:
            errors.append(f'{k} state change >15%: {prior:,} -> {current:,}')
        if k[0]=='country' and prior>=5000 and abs(current/prior-1)>.60:
            errors.append(f'{k} large country change >60%: {prior:,} -> {current:,}')
        if k[0]=='country' and prior>=500 and abs(current/prior-1)>1.5:
            errors.append(f'{k} country changed >150%: {prior:,} -> {current:,}')
    if us_country is None:
        errors.append('Could not verify separate published US country total')
    elif abs(new_us/us_country-1)>.01:
        errors.append(f'50-state sum {new_us:,} differs >1% from US country total {us_country:,}')
    if errors:
        raise ValidationError('\n'.join(errors))
    return {'countries':sum(k[0]=='country' for k in candidate),'states_changed':states_changed,
            'countries_changed':countries_changed,'us_total':new_us,'world_total':new_world}

def collect_annual(year:int, previous: dict) -> tuple[dict, dict]:
    world_html=get(WORLD_URL)
    world=membership_from_html(world_html,kind='world',expected_year=year)
    candidate={('world','Worldwide'):dict(scope='world',name='Worldwide',members=world,source_url=WORLD_URL)}
    country_pages=discover_country_pages()
    failures={}
    jobs=[('country',it) for it in country_pages.items()]+[('state',n) for n in STATE_NAMES]
    jobs.append(('us',('United States',country_pages.get('United States',COUNTRY_PREFIX+'united-states'))))
    us_country=None
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures={pool.submit(fetch_country,payload,year) if scope=='country' else
                 pool.submit(fetch_state,payload) if scope=='state' else
                 pool.submit(fetch_country,payload,year): (scope,payload)
                 for scope,payload in jobs}
        for future in as_completed(futures):
            scope,payload=futures[future]
            try:
                key,row=future.result()
                if scope=='us':
                    us_country=row['members']
                elif scope=='country' and key[1]=='United States':
                    us_country=row['members']
                elif key in candidate:
                    failures[str(key)]='Duplicate geography'
                else:
                    candidate[key]=row
            except Exception as exc:
                ident=payload[0] if isinstance(payload,tuple) else payload
                failures[f'{scope}:{ident}']=str(exc)
    # Candidate data and source failures are only uploaded to GitHub Actions
    # diagnostic artifacts. They are never added to membership_data/ or Pages.
    REPORTS.mkdir(parents=True,exist_ok=True)
    (REPORTS/f'candidate_{year}.csv').write_bytes(csv_bytes(candidate))
    (REPORTS/f'fetch_failures_{year}.json').write_text(
        json.dumps(failures,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    # Zero/non-disclosed on optional countries is tolerated only if absent from
    # previous snapshots, so it cannot replace a previously known denominator.
    critical={k:v for k,v in failures.items() if k.startswith('state:') or
              k=='country:United States' or
              (k.startswith('country:') and ('country',k.partition(':')[2]) in previous)}
    if critical:
        raise ValidationError('Incomplete annual country/state fetch:\n'+json.dumps(critical,indent=2))
    checks=validate_candidate(candidate,previous,year,country_pages,us_country)
    checks['unpublished_or_unavailable_countries']=failures
    return candidate,checks

def annual(directory: Path=SNAPSHOTS,today:date|None=None,force:bool=False) -> dict:
    today=today or date.today()
    year=today.year-1
    path=directory/f'{year}.csv'
    if path.exists():
        return {'status':'already_published','year':year}
    if not force and retry_day(today) is None:
        return {'status':'not_scheduled','date':today.isoformat()}
    previous_file=directory/f'{year-1}.csv'
    if not previous_file.exists():
        raise ValidationError(f'Missing previous snapshot {previous_file}')
    previous=read_csv(previous_file)
    if len([k for k in previous if k[0]=='country'])<MIN_COUNTRIES:
        raise ValidationError('Baseline country coverage incomplete: run bootstrap workflow')
    candidate,checks=collect_annual(year,previous)
    # Ensure all previously published country membership remains present.
    # New countries can appear in this year even if older years lack them.
    validate_snapshot(candidate,year)
    if path.exists():
        raise ValidationError(f'Refusing to overwrite existing snapshot {path}')
    write_snapshot_atomic(path,candidate)
    return {'status':'published','year':year,'checks':checks}

def report(payload:dict, folder:Path=REPORTS):
    folder.mkdir(exist_ok=True,parents=True)
    (folder/'last_attempt.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(payload,indent=2,ensure_ascii=False),flush=True)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['bootstrap','annual','due'])
    parser.add_argument('--membership-dir',type=Path,default=SNAPSHOTS)
    parser.add_argument('--today',type=date.fromisoformat,default=date.today())
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args(argv)
    try:
        if args.command=='bootstrap':
            result=bootstrap(args.membership_dir)
        elif args.command=='due':
            index=retry_day(args.today)
            result={'date':args.today.isoformat(),'retry_day':index,'due':index is not None,
                    'second_monday':second_monday(args.today.year).isoformat()}
        else:
            result=annual(args.membership_dir,args.today,args.force)
        report(result)
        return 0
    except Exception as exc:
        report({'status':'failed','date':args.today.isoformat(),'error':str(exc),'command':args.command})
        print(f'ERROR: {exc}',file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
