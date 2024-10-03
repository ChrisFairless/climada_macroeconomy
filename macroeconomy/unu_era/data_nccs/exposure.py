import pycountry
from nccs.pipeline.direct.direct import get_sector_exposure

# WARNING: These functions rely on the nccs-supply-chain package which is in active development
# The package currently downloads much of its data from a private Amazon S3 bucket, meaning these 
# methods will fail. The project is an open source one funded by the Swiss government and the 
# data is planned (as of September 2024) to be made available through the ETH servers in 2025, 
# most likely through the CLIMADA Data API.
# 
# Contact chrisfairless@hotmail.com for the latest on this data or to request a free copy for 
# commercial or noncommercial use.

def get_nccs_sector_exposure(country, sector):
    sector = 'service' if sector == 'services' else sector
    return get_sector_exposure(sector, country)

