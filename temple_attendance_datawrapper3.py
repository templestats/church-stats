
        dashboard_rows = build_dashboard_trends(
            located,
            memberships,
            first_date,
            window_end,
        )

        write_json(
            args.output_dir
            / "trend_dashboard.json",
            dashboard_rows,
        )

        print(
            f"Dashboard trend rows: "
            f"{len(dashboard_rows):,}"
        )

        # ----------------------------------------------------
        # Canonical daily raw dataset
        # ----------------------------------------------------

        raw_rows = [
            {
                "date": row.activity_date.isoformat(),
                "temple": row.temple,
                "endowments": row.endowments,
                "living": row.living,
                "scope": geography.scope,
                "geography": geography.name,
            }
            for row, geography in located
        ]

        write_csv(
            args.output_dir
            / "fuller_consideration_daily.csv",
            raw_rows,
        )

        print()

        print(
            f"Current window endowments: "
            f"{world_endowments:,}"
        )

        print(
            f"Worldwide annualized endowments/member: "
            f"{world_rate:.3f}"
        )

        print(
            f"U.S. annualized endowments/member: "
            f"{us_rate:.3f}"
        )

        print(
            f"Annualized living endowments/eligible member: "
            f"{eligible_rate:.1%}"
        )

        print(
            f"Trend rows: {len(trend_rows):,} "
            f"(starts "
            f"{trend_rows[0]['run_date'] if trend_rows else 'n/a'})"
        )

        print(
            f"CSV/JSON outputs: "
            f"{args.output_dir.resolve()}"
        )

        if args.skip_datawrapper:
            print(
                "Skipping Datawrapper update "
                "(--skip-datawrapper)."
            )
        else:
            update_datawrapper(
                session,
                args.output_dir,
                window_start,
                window_end,
            )

        return 0

    except (
        requests.RequestException,
        RuntimeError,
        ValueError,
        KeyError,
    ) as error:
        print(
            f"Error: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
