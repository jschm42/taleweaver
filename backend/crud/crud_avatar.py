from backend.crud.base import CRUDBase
from backend.models.avatar import Avatar
from backend.schemas.avatar import AvatarCreate, AvatarUpdate


class CRUDAvatar(CRUDBase[Avatar, AvatarCreate, AvatarUpdate]):
    pass

avatar = CRUDAvatar(Avatar)
