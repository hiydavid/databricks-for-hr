"""Command line entry point: ``python -m generate --mode seed ...``."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date

from . import datasets
from .dates import iso, yesterday
from .rng import sub_rng
from .world import World
from .writer import STATE_DIR, load_state, save_state, write_dataset


def build_world(num_employees: int, seed: int, mode: str, end_date: date,
                start: date = None, anchor: date = None) -> World:
    world = World(num_employees, seed, end_date, mode=mode, start=start, anchor=anchor)
    world.build_static()
    world.create_initial_workers()
    world.assign_workers()
    world.plan_patterns()
    world.simulate()
    world.finalize_events()
    return world


def _write_all(world, rows, ground_truth, output, mode, since=None) -> list:
    written = []
    for dataset, ds_rows in rows.items():
        field = datasets.DATE_FIELD.get(dataset)
        if since is not None:
            if dataset in datasets.STATIC:
                continue
            if field is None:
                continue
            ds_rows = [r for r in ds_rows if r.get(field, "") > since]
        if not ds_rows:
            continue
        path = write_dataset(output, dataset, mode, world.T, ds_rows)
        written.append(path)
    if ground_truth:
        gt = ground_truth
        if since is not None:
            gt = [g for g in gt if g["termination_date"] > since]
        if gt:
            path = write_dataset(output, "_ground_truth/exit_reasons", mode, world.T, gt)
            written.append(path)
    return written


def run(mode: str, num_employees: int | None, seed: int | None, output: str,
        end_date: date | None = None) -> list:
    end_date = min(end_date or yesterday(), yesterday())
    if mode == "seed":
        num_employees = 5000 if num_employees is None else num_employees
        seed = 42 if seed is None else seed
        world = build_world(num_employees, seed, mode, end_date)
        rows, ground_truth = datasets.build_rows(world)
        datasets.apply_defects(world, rows, ground_truth, sub_rng(seed, "defects"))
        written = _write_all(world, rows, ground_truth, output, mode)
        state = dict(start=iso(world.start), last_date=iso(world.T), seed=seed,
                     anchor_date=iso(world.anchor),
                     num_employees=num_employees, mode=mode)
        save_state(output, state)
        manifest_dir = os.path.join(output, STATE_DIR)
        os.makedirs(manifest_dir, exist_ok=True)
        with open(os.path.join(manifest_dir, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(world.manifest, fh, indent=2, sort_keys=True)
        return written

    state = load_state(output)
    if state is None:
        raise SystemExit("no _state/state.json found; run --mode seed first")
    if num_employees is not None and num_employees != state["num_employees"]:
        raise SystemExit("increment mode uses the seeded num_employees "
                         f"({state['num_employees']}); omit --num-employees")
    if seed is not None and seed != state["seed"]:
        raise SystemExit(f"increment mode uses the seeded value ({state['seed']}); "
                         "omit --seed")
    start = date.fromisoformat(state["start"])
    last = date.fromisoformat(state["last_date"])
    anchor = date.fromisoformat(state.get("anchor_date", state["last_date"]))
    if end_date <= last:
        return []
    world = build_world(state["num_employees"], state["seed"], "increment", end_date,
                        start=start, anchor=anchor)
    rows, ground_truth = datasets.build_rows(world)
    written = _write_all(world, rows, ground_truth, output, mode, since=state["last_date"])
    state["last_date"] = iso(end_date)
    state["mode"] = mode
    save_state(output, state)
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(prog="generate")
    parser.add_argument("--mode", choices=["seed", "increment"], default="seed")
    parser.add_argument("--num-employees", type=int, default=None,
                        help="seed only; increments reuse the seeded value")
    parser.add_argument("--seed", type=int, default=None,
                        help="seed only; increments reuse the seeded value")
    parser.add_argument("--output", required=True)
    parser.add_argument("--end-date", default=None,
                        help="override the seed end date (yyyy-mm-dd); defaults to yesterday")
    args = parser.parse_args(argv)
    end_date = date.fromisoformat(args.end_date) if args.end_date else None
    if end_date and end_date > yesterday():
        print(f"end date capped at yesterday ({yesterday()})")
    written = run(args.mode, args.num_employees, args.seed, args.output, end_date)
    n = args.num_employees or 5000
    if args.mode == "increment":
        state = load_state(args.output) or {}
        n = state.get("num_employees", n)
    print(f"mode={args.mode} employees={n} files={len(written)}")
    for path in written:
        print("  " + path)


if __name__ == "__main__":
    main()
