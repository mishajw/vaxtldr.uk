import pandas as pd

# Source: https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates/bulletins/annualmidyearpopulationestimates/mid2019estimates#population-growth-in-england-wales-scotland-and-northern-ireland
__ENGLAND_POPULATION = 56_286_961
# Source: https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2021/02/COVID-19-weekly-announced-vaccinations-11-February-2021.xlsx
__ENGLAND_OVER_80_POPULATION = 2_836_964

__POPULATION_BY_GROUP = {
    "<80": __ENGLAND_POPULATION - __ENGLAND_OVER_80_POPULATION,
    ">=80": __ENGLAND_OVER_80_POPULATION,
    "all": __ENGLAND_POPULATION,
}


def add_population(df: pd.DataFrame) -> pd.DataFrame:
    df["population"] = df["group"].apply(lambda group: __POPULATION_BY_GROUP[group])
    return df
