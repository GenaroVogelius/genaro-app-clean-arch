from fastapi import APIRouter, HTTPException, status

from app.config.settings import Settings
from app.domain.aggregates.item import Item
from app.domain.simple_entities.status import StatusType
from app.domain.use_cases.item.create_item.create_item_use_case import (
    CreateItemUseCase,
)
from app.domain.use_cases.item.get_item.get_item_use_case import GetItemUseCase
from app.infrastructure.api.schemas.item_schemas import CreateItemRequest, ItemResponse
from app.infrastructure.db.mongo.repositories.item_repository.item_repository import (
    ItemRepository,
)


class MainRoutes:
    def __init__(self):
        self.router = APIRouter()
        self.settings = Settings()

        # implementations of ports
        item_repository = ItemRepository()
        self.create_item_use_case = CreateItemUseCase(repository=item_repository)
        self.get_item_use_case = GetItemUseCase(repository=item_repository)

        self._setup_routes()

    def _setup_routes(self):
        @self.router.get("/health")
        async def health_check():
            """Health check endpoint - Public access"""
            return {
                "status": "healthy",
                "service": self.settings.APP_NAME,
                "version": self.settings.VERSION,
            }

        @self.router.post(
            "/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED
        )
        async def create_item(payload: CreateItemRequest):
            """Create a new item"""
            item = Item(name=payload.name)
            result = await self.create_item_use_case.execute(item)
            if result.status == StatusType.ERROR:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=result.message,
                )
            return ItemResponse(**item.model_dump())

        @self.router.get("/items/{item_id}", response_model=ItemResponse)
        async def get_item(item_id: str):
            """Get an item by id"""
            item = await self.get_item_use_case.execute(item_id)
            if item is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
                )
            return ItemResponse(**item.model_dump())
