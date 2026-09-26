from datetime import date

from pydantic import BaseModel, model_validator


class DateRangeValidator(BaseModel):
    date_from: date
    date_to: date

    @model_validator(mode="after")
    def check_date(self):
        if self.date_from > self.date_to:
            raise ValueError("date_from must be less than or equal to date_to")
        return self
