import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///cdisc_curation.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CDISC_API_KEY = os.environ.get("CDISC_API_KEY", "")
    # Preferred over CDISC_API_KEY when set (Ocp-Apim-Subscription-Key header)
    CDISC_SUBSCRIPTION_KEY = os.environ.get("CDISC_SUBSCRIPTION_KEY", "")
    CDISC_API_BASE_URL = "https://api.library.cdisc.org/api/cosmos/v2"
    NCIT_API_BASE_URL = "https://api-evsrest.nci.nih.gov/api/v1"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB upload limit
    PORT = int(os.environ.get("PORT", 8081))
    ALIGNMENT_SUBMODULE_DIR = os.environ.get(
        "ALIGNMENT_SUBMODULE_DIR",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "cdisc-bc-ncit-alignment"),
    )
