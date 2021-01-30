import pandas as pd

# Source: https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationprojections/datasets/tablea21principalprojectionukpopulationinagegroups
__POPULATION_BY_GROUP = {
    "<80": 64094000,
    ">=80": 3497000,
    "all": 64094000 + 3497000,
}


def add_population(df: pd.DataFrame) -> pd.DataFrame:
    df["population"] = df["group"].apply(lambda group: __POPULATION_BY_GROUP[group])
    return df
