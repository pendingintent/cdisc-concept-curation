import logging
import os
import requests

logger = logging.getLogger(__name__)

LOINC_EF_FIELDS = (
    "LOINC_NUM,SHORTNAME,LONG_COMMON_NAME,RELATEDNAMES2,PROPERTY,"
    "METHOD_TYP,AnswerLists,units,datatype,isCopyrighted,"
    "containsCopyrighted,CONSUMER_NAME,COMPONENT,"
    "EXTERNAL_COPYRIGHT_NOTICE,EXTERNAL_COPYRIGHT_LINK"
)


class LoincApiClient:
    BASE_URL = "https://clinicaltables.nlm.nih.gov/api/loinc_items/v3/search"

    def _auth(self):
        user = os.environ.get("LOINC_USER")
        password = os.environ.get("LOINC_PASSWORD")
        if user and password:
            return (user, password)
        return None

    def search(self, term, size=10):
        """Search LOINC by code or name. Returns a list of dicts with all LOINC fields.

        Uses the ef (extra fields) parameter so all field values are returned.
        Response format: [total, [codes], {field: [values, ...]}, display_data]
        """
        try:
            response = requests.get(
                self.BASE_URL,
                params={"ef": LOINC_EF_FIELDS, "terms": term, "maxList": size},
                auth=self._auth(),
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            # response[1] = list of internal codes (length = number of results)
            # response[2] = dict of {field_name: [value_per_result, ...]}
            codes = data[1] if len(data) > 1 and data[1] else []
            extra = data[2] if len(data) > 2 and data[2] else {}
            results = []
            for i in range(len(codes)):
                item = {}
                for field, values in extra.items():
                    item[field] = values[i] if values and i < len(values) else None
                results.append(item)
            return results
        except (requests.RequestException, ValueError, IndexError, TypeError) as e:
            # Index/Type errors cover the positional parsing of the NLM
            # array response ([total, [codes], {field: values}, ...]).
            logger.error("LOINC search failed for term %r: %s", term, e)
            return [{"error": str(e)}]
