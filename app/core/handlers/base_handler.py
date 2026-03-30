from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseHandler(ABC):
    """Abstract base class for query handlers.

    All input type handlers (text, image, etc.) should inherit from this class
    and implement the required methods for validation and processing.
    """

    @abstractmethod
    def validate(self, input_data: Any) -> None:
        """Validate the input data.

        Args:
            input_data: The input data to validate

        Raises:
            ValueError: If validation fails
        """
        pass

    @abstractmethod
    async def process(self, input_data: Any, *args, **kwargs) -> Dict[str, Any]:
        """Process the input and return the result.

        Args:
            input_data: The input data to process

        Returns:
            A dictionary containing the processing result
        """
        pass
