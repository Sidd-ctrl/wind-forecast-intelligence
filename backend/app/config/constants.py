from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
UTC_LABEL = "UTC"
MW_UNIT = "MW"

ACTUAL_DATASET = "FUELHH"
FORECAST_DATASET = "WINDFOR"
WIND_FUEL_TYPE = "WIND"

ACTUAL_SOURCE_URL = "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH"
FORECAST_SOURCE_URL = "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR"
ACTUAL_ENDPOINT_PATH = "/datasets/FUELHH"
FORECAST_ENDPOINT_PATH = "/datasets/WINDFOR"

PERIOD_MINUTES = 30
HOUR_MINUTES = 60

CUTOFF_MODE_ROLLING = "rolling_lead"
CUTOFF_MODE_ABSOLUTE = "absolute_cutoff"

STATUS_MATCHED = "matched"
STATUS_MISSING_FORECAST = "missing_forecast"
STATUS_MISSING_ACTUAL = "missing_actual"
STATUS_MISSING_BOTH = "missing_both"

ASSIGNMENT_SCOPE_NOTE = (
    "Wind generation shortfall is not the utility's total procurement requirement. "
    "Consumer demand, other generation sources and wholesale prices are outside the scope of this analysis."
)
