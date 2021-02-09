import pandas as pd

# Source: https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationprojections/datasets/tablea21principalprojectionukpopulationinagegroups
__UK_OVER_80_FRACTION = 3497000 / (3497000 + 64094000)
# Source: https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates/bulletins/annualmidyearpopulationestimates/mid2019estimates#population-growth-in-england-wales-scotland-and-northern-ireland
__ENGLAND_POPULATION = 56286961

__POPULATION_BY_GROUP = {
    "<80": int(__ENGLAND_POPULATION * (1 - __UK_OVER_80_FRACTION)),
    ">=80": int(__ENGLAND_POPULATION * __UK_OVER_80_FRACTION),
    "all": __ENGLAND_POPULATION,
}


def add_population(df: pd.DataFrame) -> pd.DataFrame:
    df["population"] = df["group"].apply(lambda group: __POPULATION_BY_GROUP[group])
    return df
