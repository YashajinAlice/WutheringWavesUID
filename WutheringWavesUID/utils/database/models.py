from typing import Any, Dict, List, Type, TypeVar, Optional

from gsuid_core.logger import logger
from sqlalchemy.sql import or_, and_
from sqlmodel import Field, col, select
from sqlalchemy import null, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from gsuid_core.utils.database.startup import exec_list
from gsuid_core.webconsole.mount_app import PageSchema, GsAdminModel, site
from gsuid_core.utils.database.base_models import (
    Bind,
    Push,
    User,
    BaseModel,
    with_session,
)

exec_list.extend(
    [
        'ALTER TABLE WavesUser ADD COLUMN platform TEXT DEFAULT ""',
        'ALTER TABLE WavesUser ADD COLUMN stamina_bg_value TEXT DEFAULT ""',
        'ALTER TABLE WavesUser ADD COLUMN bbs_sign_switch TEXT DEFAULT "off"',
        'ALTER TABLE WavesUser ADD COLUMN bat TEXT DEFAULT ""',
        'ALTER TABLE WavesUser ADD COLUMN did TEXT DEFAULT ""',
        'ALTER TABLE WavesPush ADD COLUMN push_time_value TEXT DEFAULT ""',
    ]
)

T_WavesBind = TypeVar("T_WavesBind", bound="WavesBind")
T_WavesUser = TypeVar("T_WavesUser", bound="WavesUser")
T_WavesUserAvatar = TypeVar("T_WavesUserAvatar", bound="WavesUserAvatar")


class WavesUserAvatar(BaseModel, table=True):
    __table_args__: Dict[str, Any] = {"extend_existing": True}
    avatar_hash: str = Field(default="", title="头像哈希")


class WavesBind(Bind, table=True):
    __table_args__: Dict[str, Any] = {"extend_existing": True}
    uid: Optional[str] = Field(default=None, title="鸣潮UID")

    @classmethod
    @with_session
    async def get_group_all_uid(
        cls: Type[T_WavesBind], session: AsyncSession, group_id: Optional[str] = None
    ):
        """根据传入`group_id`获取该群号下所有绑定`uid`列表"""
        result = await session.scalars(
            select(cls).where(col(cls.group_id).contains(group_id))
        )
        return result.all()

    @classmethod
    @with_session
    async def check_uid_exists_globally(
        cls: Type[T_WavesBind], session: AsyncSession, uid: str
    ) -> Optional[T_WavesBind]:
        """
        檢查UID是否已被任何用戶綁定（全局檢查）
        
        Args:
            uid: 要檢查的UID
            
        Returns:
            如果UID已被綁定，返回綁定記錄；否則返回None
        """
        # 查詢所有包含此UID的綁定記錄
        sql = select(cls).where(
            or_(
                col(cls.uid) == uid,  # 直接匹配
                col(cls.uid).like(f"%{uid}%")  # 包含在UID列表中
            )
        )
        result = await session.execute(sql)
        data = result.scalars().all()
        
        # 檢查是否真的包含此UID（因為like可能匹配到其他UID）
        for bind_record in data:
            if bind_record.uid:
                uid_list = bind_record.uid.split("_")
                if uid in uid_list:
                    return bind_record
        
        return None

    @classmethod
    @with_session
    async def get_uid_bind_info(
        cls: Type[T_WavesBind], session: AsyncSession, uid: str
    ) -> Optional[Dict[str, Any]]:
        """
        獲取UID綁定信息（管理員查詢用）
        
        Args:
            uid: 要查詢的UID
            
        Returns:
            包含綁定信息的字典，如果未綁定則返回None
        """
        bind_record = await cls.check_uid_exists_globally(uid)
        if not bind_record:
            return None
        
        return {
            "uid": uid,
            "user_id": bind_record.user_id,
            "bot_id": bind_record.bot_id,
            "group_id": bind_record.group_id,
            "bind_time": getattr(bind_record, 'bind_time', None) or getattr(bind_record, 'created_time', None) or 0,
            "all_uids": bind_record.uid.split("_") if bind_record.uid else []
        }

    @classmethod
    async def insert_waves_uid(
        cls: Type[T_WavesBind],
        user_id: str,
        bot_id: str,
        uid: str,
        group_id: Optional[str] = None,
        lenth_limit: Optional[int] = None,
        is_digit: Optional[bool] = True,
        game_name: Optional[str] = None,
    ) -> int:
        if lenth_limit:
            if len(uid) != lenth_limit:
                return -1

        if is_digit:
            if not uid.isdigit():
                return -3
        if not uid:
            return -1

        # 檢查UID是否已被其他用戶綁定
        existing_bind = await cls.check_uid_exists_globally(uid)
        if existing_bind and existing_bind.user_id != user_id:
            return -4  # UID已被其他用戶綁定

        # 第一次绑定
        if not await cls.bind_exists(user_id, bot_id):
            code = await cls.insert_data(
                user_id=user_id,
                bot_id=bot_id,
                **{"uid": uid, "group_id": group_id},
            )
            return code

        result = await cls.select_data(user_id, bot_id)
        # await user_bind_cache.set(user_id, result)

        uid_list = result.uid.split("_") if result and result.uid else []
        uid_list = [i for i in uid_list if i] if uid_list else []

        # 已经绑定了该UID
        res = 0 if uid not in uid_list else -2

        # 强制更新库表
        force_update = False
        if uid not in uid_list:
            uid_list.append(uid)
            force_update = True
        new_uid = "_".join(uid_list)

        group_list = result.group_id.split("_") if result and result.group_id else []
        group_list = [i for i in group_list if i] if group_list else []

        if group_id and group_id not in group_list:
            group_list.append(group_id)
            force_update = True
        new_group_id = "_".join(group_list)

        if force_update:
            await cls.update_data(
                user_id=user_id,
                bot_id=bot_id,
                **{"uid": new_uid, "group_id": new_group_id},
            )
        return res


class WavesUser(User, table=True):
    __table_args__: Dict[str, Any] = {"extend_existing": True}
    cookie: str = Field(default="", title="Cookie")
    uid: str = Field(default=None, title="鸣潮UID")
    record_id: Optional[str] = Field(default=None, title="鸣潮记录ID")
    platform: str = Field(default="", title="ck平台")
    stamina_bg_value: str = Field(default="", title="体力背景")
    bbs_sign_switch: str = Field(default="off", title="自动社区签到")
    bat: str = Field(default="", title="bat")
    did: str = Field(default="", title="did")

    @classmethod
    @with_session
    async def mark_cookie_invalid(
        cls: Type[T_WavesUser], session: AsyncSession, uid: str, cookie: str, mark: str
    ):
        sql = (
            update(cls)
            .where(col(cls.uid) == uid)
            .where(col(cls.cookie) == cookie)
            .values(status=mark)
        )
        await session.execute(sql)
        return True

    @classmethod
    @with_session
    async def select_cookie(
        cls: Type[T_WavesUser],
        session: AsyncSession,
        uid: str,
        user_id: str,
        bot_id: str,
    ) -> Optional[str]:
        sql = select(cls).where(
            cls.user_id == user_id,
            cls.uid == uid,
            cls.bot_id == bot_id,
        )
        result = await session.execute(sql)
        data = result.scalars().all()
        return data[0].cookie if data else None

    @classmethod
    @with_session
    async def select_waves_user(
        cls: Type[T_WavesUser],
        session: AsyncSession,
        uid: str,
        user_id: str,
        bot_id: str,
    ) -> Optional[T_WavesUser]:
        sql = select(cls).where(
            cls.user_id == user_id,
            cls.uid == uid,
            cls.bot_id == bot_id,
        )
        result = await session.execute(sql)
        data = result.scalars().all()
        return data[0] if data else None

    @classmethod
    @with_session
    async def select_user_cookie_uids(
        cls: Type[T_WavesUser],
        session: AsyncSession,
        user_id: str,
    ) -> List[str]:
        sql = select(cls).where(
            and_(
                col(cls.user_id) == user_id,
                col(cls.cookie) != null(),
                col(cls.cookie) != "",
                or_(col(cls.status) == null(), col(cls.status) == ""),
            )
        )
        result = await session.execute(sql)
        data = result.scalars().all()
        return [i.uid for i in data] if data else []

    @classmethod
    @with_session
    async def select_data_by_cookie(
        cls: Type[T_WavesUser], session: AsyncSession, cookie: str
    ) -> Optional[T_WavesUser]:
        sql = select(cls).where(cls.cookie == cookie)
        result = await session.execute(sql)
        data = result.scalars().all()
        return data[0] if data else None

    @classmethod
    @with_session
    async def select_data_by_cookie_and_uid(
        cls: Type[T_WavesUser], session: AsyncSession, cookie: str, uid: str
    ) -> Optional[T_WavesUser]:
        sql = select(cls).where(cls.cookie == cookie, cls.uid == uid)
        result = await session.execute(sql)
        data = result.scalars().all()
        return data[0] if data else None

    @classmethod
    async def get_user_by_attr(
        cls: Type[T_WavesUser],
        user_id: str,
        bot_id: str,
        attr_key: str,
        attr_value: str,
    ) -> Optional[Any]:
        user_list = await cls.select_data_list(user_id=user_id, bot_id=bot_id)
        if not user_list:
            return None
        for user in user_list:
            if getattr(user, attr_key) != attr_value:
                continue
            return user

    @classmethod
    @with_session
    async def get_waves_all_user(
        cls: Type[T_WavesUser], session: AsyncSession
    ) -> List[T_WavesUser]:
        """获取所有有效用户"""
        sql = select(cls).where(
            and_(
                or_(col(cls.status) == null(), col(cls.status) == ""),
                col(cls.cookie) != null(),
                col(cls.cookie) != "",
            )
        )

        result = await session.execute(sql)
        data = result.scalars().all()
        return list(data)

    @classmethod
    async def get_all_push_user_list(cls: Type[T_WavesUser]) -> List[T_WavesUser]:
        data = await cls.get_waves_all_user()
        logger.info(f"[鸣潮] 获取到所有用户数量: {len(data)}")

        # 調試信息：檢查每個用戶的 push_switch 狀態
        for user in data:
            logger.info(
                f"[鸣潮] 用户 {user.uid} push_switch: {getattr(user, 'push_switch', 'N/A')}"
            )

        result = [user for user in data if getattr(user, "push_switch", "off") != "off"]
        logger.info(f"[鸣潮] 推送用户数量: {len(result)}")
        return result

    @classmethod
    @with_session
    async def delete_all_invalid_cookie(cls, session: AsyncSession):
        """删除所有无效缓存"""
        sql = delete(cls).where(
            or_(col(cls.status) == "无效", col(cls.cookie) == ""),
        )
        result = await session.execute(sql)
        return result.rowcount

    @classmethod
    @with_session
    async def delete_cookie(
        cls,
        session: AsyncSession,
        uid: str,
        user_id: str,
        bot_id: str,
    ):
        sql = delete(cls).where(
            and_(
                col(cls.user_id) == user_id,
                col(cls.uid) == uid,
                col(cls.bot_id) == bot_id,
            )
        )
        result = await session.execute(sql)
        return result.rowcount


class WavesPush(Push, table=True):
    __table_args__: Dict[str, Any] = {"extend_existing": True}
    bot_id: str = Field(title="平台")
    uid: str = Field(default=None, title="鸣潮UID")
    resin_push: Optional[str] = Field(
        title="体力推送",
        default="off",
        schema_extra={"json_schema_extra": {"hint": "ww开启体力推送"}},
    )
    resin_value: Optional[int] = Field(title="体力阈值", default=180)
    push_time_value: Optional[str] = Field(title="推送时间", default="")
    resin_is_push: Optional[str] = Field(title="体力是否已推送", default="off")

    @classmethod
    @with_session
    async def get_all_push_user_list(cls, session: AsyncSession):
        """獲取所有需要推送的用戶（resin_push != 'off' 且 resin_is_push == 'off'）"""
        sql = select(cls).where(
            and_(col(cls.resin_push) != "off", col(cls.resin_is_push) == "off")
        )
        result = await session.execute(sql)
        data = result.scalars().all()
        logger.info(f"[鸣潮] WavesPush 表中找到 {len(data)} 个需要推送的用户")
        return list(data)


@site.register_admin
class WavesBindAdmin(GsAdminModel):
    pk_name = "id"
    page_schema = PageSchema(
        label="鸣潮绑定管理",
        icon="fa fa-users",
    )  # type: ignore

    # 配置管理模型
    model = WavesBind


@site.register_admin
class WavesUserAdmin(GsAdminModel):
    pk_name = "id"
    page_schema = PageSchema(
        label="鸣潮用户管理",
        icon="fa fa-users",
    )  # type: ignore

    # 配置管理模型
    model = WavesUser


@site.register_admin
class WavesPushAdmin(GsAdminModel):
    pk_name = "id"
    page_schema = PageSchema(label="鸣潮推送管理", icon="fa fa-bullhorn")  # type: ignore

    # 配置管理模型
    model = WavesPush


@site.register_admin
class UserAvatar(GsAdminModel):
    pk_name = "id"
    page_schema = PageSchema(label="用户哈希管理", icon="fa fa-bullhorn")  # type: ignore

    # 配置管理模型
    model = WavesUserAvatar
