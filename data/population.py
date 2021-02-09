import pandas as pd

# Source: https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationprojections/datasets/tablea21principalprojectionukpopulationinagegroups
UK_OVER_80_FRACTION = 3497000 / (3497000 + 64094000)
# Source: https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates/bulletins/annualmidyearpopulationestimates/mid2019estimates#population-growth-in-england-wales-scotland-and-northern-ireland
ENGLAND_POPULATION = 56286961

__POPULATION_BY_GROUP = {
    "<80": ENGLAND_POPULATION * (1 - UK_OVER_80_FRACTION),
    ">=80": ENGLAND_POPULATION * UK_OVER_80_FRACTION,
    "all": ENGLAND_POPULATION,
}


def add_population(df: pd.DataFrame) -> pd.DataFrame:
    df["population"] = df["group"].apply(lambda group: __POPULATION_BY_GROUP[group])
    return df
