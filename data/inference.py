import itertools
from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta
from typing import Iterable, List

from data import population
from data.types import Source, Vaccinated, Dose, Slice, ALL_AGES, ALL_LOCATIONS

__SLICE_DIMS = ["dose", "group", "location"]
__FIRST_DAILY_DATA = date(2021, 1, 9)


def add_deaggregates(vaccinated: List[Vaccinated]) -> List[Vaccinated]:
    deaggregates = []
    vaccinated_daily = [v for v in vaccinated if v.source.period == "daily"]
    for dim in __SLICE_DIMS:
        other_dims = [d for d in __SLICE_DIMS if d != dim]

        for real_date in {v.source.real_date for v in vaccinated_daily}:
            vaccinated_on_date = [v for v in vaccinated_daily if v.source.real_date == real_date]

            aggregates = [v for v in vaccinated_on_date if getattr(v.slice, dim).is_all()]

            for aggregate in aggregates:
                unaggregates = [
                    v
                    for v in vaccinated_on_date
                    if not getattr(v.slice, dim).is_all()
                    and all(
                        getattr(v.slice, other_dim) == getattr(aggregate.slice, other_dim)
                        and not getattr(v.slice, other_dim).is_all()
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
        if v.slice.group.is_all() or v.slice.dose.is_all():
            continue
        if not v.slice.location.is_all():
            # TODO: Verify that we can remove deagg'd location data.
            continue
        if v.source.real_date >= __FIRST_DAILY_DATA and v.source.period == "weekly":
            continue
        yield v


def make_non_cumulative(vaccinated: List[Vaccinated]) -> Iterable[Vaccinated]:
    slices = {v.slice for v in vaccinated}
    for slice_ in slices:
        vs = [v for v in vaccinated if v.slice == slice_]
        vs = sorted(vs, key=lambda v: v.source.real_date)
        yield vs[0]
        for v1, v2 in zip(vs, vs[1:]):
            # assert v1.vaccinated <= v2.vaccinated, slice_
            yield replace(v2, vaccinated=v2.vaccinated - v1.vaccinated)


def make_cumulative(vaccinated: List[Vaccinated]) -> Iterable[Vaccinated]:
    slices = {v.slice for v in vaccinated}
    for slice_ in slices:
        vs = [v for v in vaccinated if v.slice == slice_]
        vs = sorted(vs, key=lambda v: v.source.real_date)
        cumulative = 0
        for v in vs:
            cumulative += v.vaccinated
            yield replace(v, vaccinated=cumulative)


def add_extrapolations(vaccinated: List[Vaccinated]) -> Iterable[Vaccinated]:
    import streamlit as st

    assert all(v.slice.location == ALL_LOCATIONS for v in vaccinated)
    assert all(v.slice.group == ALL_AGES for v in vaccinated)

    dose_1_vaccinations = {
        v.source.real_date: v.vaccinated for v in vaccinated if v.slice.dose == Dose.DOSE_1
    }
    dose_1_vaccinations_dates = list(sorted(dose_1_vaccinations.keys()))
    dose_1_new_vaccinations = {
        dose_1_vaccinations_dates[0]: dose_1_vaccinations[dose_1_vaccinations_dates[0]]
    }
    for d1, d2 in zip(dose_1_vaccinations_dates, dose_1_vaccinations_dates[1:]):
        st.write(d1, d2, dose_1_vaccinations[d1], dose_1_vaccinations[d2])
        dose_1_new_vaccinations[d2] = dose_1_vaccinations[d2] - dose_1_vaccinations[d1]
    dose_1_new_vaccinations = defaultdict(int, dose_1_new_vaccinations)
    st.write({str(k): v for k, v in dose_1_new_vaccinations.items()})

    date_latest = max(v.source.real_date for v in vaccinated)
    this_week_vaccinations = sum(
        v.vaccinated for v in vaccinated if v.source.real_date == date_latest
    )
    last_week_vaccinations = sum(
        v.vaccinated for v in vaccinated if v.source.real_date == date_latest - timedelta(weeks=1)
    )
    vaccination_rate = this_week_vaccinations - last_week_vaccinations
    st.write("last week", last_week_vaccinations)
    st.write("this week", this_week_vaccinations)
    st.write("vaccination rate", vaccination_rate)

    cumulative_dose_1_vaccinations = next(
        v.vaccinated
        for v in vaccinated
        if v.source.real_date == date_latest and v.slice.dose == Dose.DOSE_1
    )
    cumulative_dose_2_vaccinations = next(
        v.vaccinated
        for v in vaccinated
        if v.source.real_date == date_latest and v.slice.dose == Dose.DOSE_2
    )
    total_population = population.total_population()
    dose_2_vaccinations_required = 0
    for day in range(365):
        current_date = date_latest + timedelta(days=day)
        new_vaccinations = int(vaccination_rate / 7)
        dose_2_vaccinations_required += dose_1_new_vaccinations[current_date - timedelta(weeks=12)]

        dose_2_vaccinations = min(max(0, dose_2_vaccinations_required), new_vaccinations)
        dose_1_vaccinations = new_vaccinations - dose_2_vaccinations
        dose_1_vaccinations = min(
            dose_1_vaccinations, total_population - cumulative_dose_1_vaccinations
        )
        if dose_1_vaccinations + dose_2_vaccinations < new_vaccinations:
            dose_2_vaccinations += new_vaccinations - (dose_1_vaccinations + dose_2_vaccinations)
            dose_2_vaccinations = min(
                dose_2_vaccinations, total_population - cumulative_dose_2_vaccinations
            )
        assert dose_1_vaccinations >= 0
        assert dose_2_vaccinations >= 0

        cumulative_dose_2_vaccinations += dose_2_vaccinations
        cumulative_dose_1_vaccinations += dose_1_vaccinations
        dose_2_vaccinations_required -= dose_2_vaccinations

        dose_1_new_vaccinations[current_date] = dose_1_vaccinations - dose_2_vaccinations
        yield Vaccinated(
            source=Source("", current_date, current_date, "weekly"),
            slice=Slice(dose=Dose.DOSE_1),
            vaccinated=cumulative_dose_1_vaccinations,
            extrapolated=True,
        )
        yield Vaccinated(
            source=Source("", current_date, current_date, "weekly"),
            slice=Slice(dose=Dose.DOSE_2),
            vaccinated=cumulative_dose_2_vaccinations,
            extrapolated=True,
        )

    yield from vaccinated


def add_dose_2_wait(vaccinated: List[Vaccinated]) -> List[Vaccinated]:
    max_date = max(v.source.real_date for v in vaccinated if not v.extrapolated)
    dose_2_wait = []
    for v in vaccinated:
        if v.slice.dose != Dose.DOSE_2:
            continue
        wait_date = v.source.real_date + timedelta(days=7)
        dose_2_wait.append(
            replace(
                v,
                slice=replace(v.slice, dose=Dose.DOSE_2_PLUS_WAIT),
                source=replace(v.source, real_date=wait_date),
                extrapolated=wait_date > max_date,
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
        if not getattr(v.slice, dim).is_all()
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

    for dim_value in {
        getattr(v.slice, dim) for v in vaccinated_weekly if v.source.real_date in dates
    }:
        ratio0 = sum(
            v for d, ddate, v in dim_date_vaccinated if ddate == dates[0] and d == dim_value
        ) / sum(v for _, ddate, v in dim_date_vaccinated if ddate == dates[0])
        ratio1 = sum(
            v for d, ddate, v in dim_date_vaccinated if ddate == dates[1] and d == dim_value
        ) / sum(v for _, ddate, v in dim_date_vaccinated if ddate == dates[1])

        date_progress = (aggregate.source.data_date - dates[0]).days / (dates[1] - dates[0]).days
        date_progress = max(0.0, min(1.0, date_progress))
        ratio = ratio0 + (ratio1 - ratio0) * date_progress
        new_vaccinated = int(aggregate.vaccinated * ratio)
        assert new_vaccinated >= 0, (
            dim,
            dim_value,
            ratio,
            ratio0,
            ratio1,
            dates,
            aggregate.source.real_date,
        )
        yield Vaccinated(
            source=aggregate.source,
            vaccinated=new_vaccinated,
            slice=replace(aggregate.slice, **{dim: dim_value}),
            interpolated=True,
        )


def aggregate_ages(vaccinated: List[Vaccinated]) -> List[Vaccinated]:
    def key(v: Vaccinated):
        return str((v.slice.location, v.slice.dose, v.source, v.extrapolated, v.interpolated))

    vaccinated = list(sorted(vaccinated, key=key))
    vaccinated_grouped_by_age = [list(vs) for _, vs in itertools.groupby(vaccinated, key=key)]
    aggd = [
        replace(
            vs[0],
            slice=replace(vs[0].slice, group=ALL_AGES),
            vaccinated=sum(v.vaccinated for v in vs),
        )
        for vs in vaccinated_grouped_by_age
    ]
    import streamlit as st

    st.write(len(vaccinated), len(aggd))
    return aggd
