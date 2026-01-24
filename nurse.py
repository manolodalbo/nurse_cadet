class NurseCadet:
    def __init__(self, data, filename):
        """Initializes the cadet object from a dictionary (JSON response)."""
        # Card Classification
        self.card_type = data.get("card_type")
        self.serial_number = data.get("serial_number")

        # Name
        self.last_name = data.get("last_name")
        self.first_name = data.get("first_name")
        self.middle_name = data.get("middle_name")

        # Home Address (300A Revised only)
        self.home_street = data.get("home_street")
        self.home_city = data.get("home_city")
        self.home_county = data.get("home_county")
        self.home_state = data.get("home_state")

        # Identification (300A Revised only)
        self.date_of_birth = data.get("date_of_birth")

        # Service History
        self.admission_corp_date = data.get("admission_corp_date")
        self.admission_school_date = data.get("admission_school_date")
        self.termination_date = data.get("termination_date")
        self.termination_type = data.get("termination_type")

        # Nursing School Details
        self.school_name = data.get("school_name")
        self.school_city = data.get("school_city")
        self.school_state = data.get("school_state")
        self.file = filename

    @staticmethod
    def get_response_schema():
        """Returns the schema for Gemini 3 Flash to ensure structured JSON output."""
        return {
            "type": "OBJECT",
            "properties": {
                "card_type": {
                    "type": "STRING",
                    "enum": ["300A", "300A Revised", "null"],
                },
                "serial_number": {"type": "STRING"},
                "last_name": {"type": "STRING"},
                "first_name": {"type": "STRING"},
                "middle_name": {"type": "STRING"},
                "home_street": {"type": "STRING"},
                "home_city": {"type": "STRING"},
                "home_county": {"type": "STRING"},
                "home_state": {"type": "STRING"},
                "date_of_birth": {"type": "STRING"},
                "admission_corp_date": {"type": "STRING"},
                "admission_school_date": {"type": "STRING"},
                "termination_date": {"type": "STRING"},
                "termination_type": {
                    "type": "STRING",
                    "enum": ["Graduation", "Withdrawal", "null"],
                },
                "school_name": {"type": "STRING"},
                "school_city": {"type": "STRING"},
                "school_state": {"type": "STRING"},
            },
            "required": [],
        }
