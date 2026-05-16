"""Singapore postal districts 1-28 (URA's standard breakdown).

The PMI search page caps result count per query, so iterating district-by-district
is the most reliable way to get full coverage of the 60-month window.
"""

DISTRICTS: dict[str, str] = {
    "01": "Raffles Place, Cecil, Marina, People's Park",
    "02": "Anson, Tanjong Pagar",
    "03": "Queenstown, Tiong Bahru",
    "04": "Telok Blangah, Harbourfront",
    "05": "Pasir Panjang, Hong Leong Garden, Clementi New Town",
    "06": "High Street, Beach Road (part)",
    "07": "Middle Road, Golden Mile",
    "08": "Little India",
    "09": "Orchard, Cairnhill, River Valley",
    "10": "Ardmore, Bukit Timah, Holland Road, Tanglin",
    "11": "Watten Estate, Novena, Thomson",
    "12": "Balestier, Toa Payoh, Serangoon",
    "13": "Macpherson, Braddell",
    "14": "Geylang, Eunos",
    "15": "Katong, Joo Chiat, Amber Road",
    "16": "Bedok, Upper East Coast, Eastwood, Kew Drive",
    "17": "Loyang, Changi",
    "18": "Tampines, Pasir Ris",
    "19": "Serangoon Garden, Hougang, Punggol",
    "20": "Bishan, Ang Mo Kio",
    "21": "Upper Bukit Timah, Clementi Park, Ulu Pandan",
    "22": "Jurong",
    "23": "Hillview, Dairy Farm, Bukit Panjang, Choa Chu Kang",
    "24": "Lim Chu Kang, Tengah",
    "25": "Kranji, Woodgrove",
    "26": "Upper Thomson, Springleaf",
    "27": "Yishun, Sembawang",
    "28": "Seletar, Yio Chu Kang",
}


def parse_district_arg(arg: str) -> list[str]:
    """Parse the --districts CLI argument: 'all' or comma-separated codes."""
    if arg.lower() == "all":
        return list(DISTRICTS.keys())
    out = []
    for token in arg.split(","):
        token = token.strip().zfill(2)
        if token not in DISTRICTS:
            raise ValueError(f"Unknown district code: {token}")
        out.append(token)
    return out
