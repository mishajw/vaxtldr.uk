from dataclasses import replace
from datetime import date, timedelta
from typing import Iterable, List

import numpy as np

from data.types import Source, Vaccinated

__SLICE_DIMS = ["dose", "group", "location"]
__FIRST_DAILY_DATA = date(2021, 1, 9)


def add_deaggregates(vaccinated: List[Vaccinated]) -> List[Vaccinated]:
    deaggregates = []
    vaccinated_daily = [v for v in vaccinated if v.source.period == "daily"]
    for dim in __SLICE_DIMS:
        other_dims = [d for d in __SLICE_DIMS if d != dim]

        for real_date in {v.source.real_date for v in vaccinated_daily}:
            vaccinated_on_date = [v for v in vaccinated_daily if v.source.real_date == real_date]

            aggregates = [v for v in vaccinated_on_date if getattr(v.slice, dim) == "all"]

            for aggregate in aggregates:
                unaggregates = [
                    v
                    for v in vaccinated_on_date
                    if getattr(v.slice, dim) != "all"
                    and all(
                        getattr(v.slice, other_dim) == getattr(aggregate.slice, other_dim)
                        and getattr(v.slice, other_dim) != "all"
                        for other_dim in other_dims
                    )
                    and v.slice.group == aggregate.slice.group
                    and v.slice.location == aggregate.slice.location
                ]
                if len(unaggregates) == 0:
                    deaggregates.extend(deaggregate_with_interpolation(aggregate, dim, vaccinated))
                    continue

                unaggregate_sum = sum(v.vaccinated for v in unaggregates)
                difference = abs(aggregate.vaccinated - unaggregate_sum)
                assert (
                    difference < 1000 or difference / unaggregate_sum < 0.05
                ), f"{aggregate.vaccinated} vs. {unaggregate_sum}"
    return vaccinated + deaggregates


def remove_aggregates(vaccinated: List[Vaccinated]) -> Iterable[Vaccinated]:
    for v in vaccinated:
        if v.slice.group == "all" or v.slice.dose == "all":
            continue
        if v.slice.location != "all":
            # TODO: Verify that we can remove deagg'd location data.
            continue
        if v.source.real_date >= __FIRST_DAILY_DATA and v.source.period == "weekly":
            continue
        yield v


def add_extrapolations(vaccinated: List[Vaccinated]) -> List[Vaccinated]:
    max_date = max(v.source.real_date for v in vaccinated)

    predictions = []
    for slice in {v.slice for v in vaccinated}:
        array = np.array(
            [
                [(v.source.real_date - max_date).days, v.vaccinated]
                for v in vaccinated
                if v.slice == slice and v.source.real_date > max_date - timedelta(days=7)
            ]
        )
        if len(array) <= 1:
            continue
        m, b = np.polyfit(array[:, 0], array[:, 1], 1)
        for plus_days in range(1, 52 * 7):
            real_date = max_date + timedelta(days=plus_days)
            predictions.append(
                Vaccinated(
                    Source("prediction", data_date=real_date, real_date=real_date, period="daily"),
                    vaccinated=m * plus_days + b,
                    slice=slice,
                    extrapolated=True,
                )
            )
    return vaccinated + predictions


def add_12w_dose_lag(vaccinated: List[Vaccinated]) -> List[Vaccinated]:
    dose1s_by_date_slice = {
        (v.source.real_date, v.slice.location, v.slice.group): v.vaccinated
        for v in vaccinated
        if v.slice.dose == "1"
    }

    new_vaccinated = []
    for v in vaccinated:
        if v.slice.dose != "2":
            new_vaccinated.append(v)
            continue
        dose2 = v

        dose1_date = dose2.source.real_date - timedelta(weeks=12)
        key = dose1_date, dose2.slice.location, dose2.slice.group
        if key not in dose1s_by_date_slice:
            new_vaccinated.append(v)
            continue
        dose1 = dose1s_by_date_slice[key]
        new_vaccinated.append(
            replace(dose2, vaccinated=dose2.vaccinated + dose1, extrapolated=True)
        )
    return new_vaccinated


def add_dose_2_wait(vaccinated: List[Vaccinated]) -> List[Vaccinated]:
    max_date = max(v.source.real_date for v in vaccinated if not v.extrapolated)
    dose_2_wait = []
    for v in vaccinated:
        if v.slice.dose != "2":
            continue
        wait_date = v.source.real_date + timedelta(weeks=2)
        dose_2_wait.append(
            replace(
                v,
                slice=replace(v.slice, dose="2_wait"),
                source=replace(v.source, real_date=wait_date),
                extrapolated=v.extrapolated or wait_date > max_date,
            )
        )
    return vaccinated + dose_2_wait


def deaggregate_with_interpolation(
    aggregate: Vaccinated, dim: str, vaccinated: List[Vaccinated]
) -> Iterable[Vaccinated]:
    other_dims = [d for d in __SLICE_DIMS if d != dim]

    vaccinated_weekly = [
        v
        for v in vaccinated
        if v.source.period == "weekly"
        if getattr(v.slice, dim) != "all"
        and all(
            getattr(v.slice, other_dim) == getattr(aggregate.slice, other_dim)
            for other_dim in other_dims
        )
    ]

    if len(vaccinated_weekly) < 2:
        print(
            f"Failed to interpolate "
            f"{aggregate.slice} {aggregate.source.real_date} "
            f"with {len(vaccinated_weekly)} samples"
        )
        yield from []
        return

    dates: List[date] = list(
        sorted(
            {v.source.real_date for v in vaccinated_weekly},
            key=lambda d: abs((d - aggregate.source.real_date).days),
        )
    )
    dates = dates[:2]
    dates = list(sorted(dates))

    dim_date_vaccinated = [
        (getattr(v.slice, dim), v.source.real_date, v.vaccinated)
        for v in vaccinated_weekly
        if v.source.real_date in dates
    ]

    for dim_value in {getattr(v.slice, dim) for v in vaccinated_weekly}:
        ratio0 = sum(
            v for d, ddate, v in dim_date_vaccinated if ddate == dates[0] and d == dim_value
        ) / sum(v for _, ddate, v in dim_date_vaccinated if ddate == dates[0])
        ratio1 = sum(
            v for d, ddate, v in dim_date_vaccinated if ddate == dates[1] and d == dim_value
        ) / sum(v for _, ddate, v in dim_date_vaccinated if ddate == dates[1])

        ratio_delta_per_day = (ratio1 - ratio0) / (dates[1] - dates[0]).days
        ratio = ratio0 + ratio_delta_per_day * (aggregate.source.data_date - dates[0]).days
        yield Vaccinated(
            source=aggregate.source,
            vaccinated=int(aggregate.vaccinated * ratio),
            slice=replace(aggregate.slice, **{dim: dim_value}),
            interpolated=True,
        )
