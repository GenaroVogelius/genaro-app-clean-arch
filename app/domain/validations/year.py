
from typing import Annotated
from pydantic import Field

Year = Annotated[int, Field(ge=1000, le=9999, strict=True)]