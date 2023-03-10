import re
import requests
from typing import Optional, Dict, Any

from ah.vendors.blizzardapi import BlizzardApi
from ah.cache import bound_cache, BoundCacheMixin, Cache
from ah.defs import SECONDS_IN

__all__ = (
    "BNAPIWrapper",
    "BNAPI",
    "GHAPI",
)


class BNAPIWrapper(BoundCacheMixin):
    def __init__(
        self, client_id: str, client_secret: str, cache: Cache, *args, **kwargs
    ) -> None:
        super().__init__(*args, cache=cache, **kwargs)
        self._api = BlizzardApi(client_id, client_secret)

    @classmethod
    def get_default_locale(cls, region: str) -> str:
        if region == "kr":
            return "ko_KR"
        elif region == "tw":
            return "zh_TW"
        else:
            return "en_US"

    @bound_cache(SECONDS_IN.WEEK)
    def get_connected_realms_index(
        self, region: str, locale: Optional[str] = None
    ) -> Any:
        if not locale:
            locale = self.get_default_locale(region)
        return self._api.wow.game_data.get_connected_realms_index(region, locale)

    @bound_cache(SECONDS_IN.WEEK)
    def get_connected_realm(
        self, region: str, connected_realm_id: int, locale: Optional[str] = None
    ) -> Any:
        if not locale:
            locale = self.get_default_locale(region)
        return self._api.wow.game_data.get_connected_realm(
            region, locale, connected_realm_id
        )

    @bound_cache(SECONDS_IN.HOUR)
    def get_auctions(
        self, region: str, connected_realm_id: int, locale: Optional[str] = None
    ) -> Any:
        if not locale:
            locale = self.get_default_locale(region)
        return self._api.wow.game_data.get_auctions(region, locale, connected_realm_id)

    @bound_cache(SECONDS_IN.HOUR)
    def get_commodities(self, region: str, locale: Optional[str] = None) -> Any:
        if not locale:
            locale = self.get_default_locale(region)
        return self._api.wow.game_data.get_commodities(region, locale)


class BNAPI:
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        cache: Optional[Cache] = None,
        wrapper=None,
        *args,
        **kwargs,
    ) -> None:
        if not wrapper:
            if not all([client_id, client_secret, cache]):
                raise ValueError(
                    "client_id, client_secret and cache must be provided "
                    "if no wrapper is provided."
                )
            self.wrapper = BNAPIWrapper(
                client_id, client_secret, cache, *args, **kwargs
            )
        else:
            self.wrapper = wrapper

    def pull_connected_realms_ids(self, region: str) -> Any:
        connected_realms = self.wrapper.get_connected_realms_index(region)
        for cr in connected_realms["connected_realms"]:
            ret = re.search(r"connected-realm/(\d+)", cr["href"])
            crid = ret.group(1)
            yield int(crid)

    def pull_connected_realm(self, region: str, crid: int) -> Any:
        """
        >>> ret = {
            # crid
            "id": 123,
            "timezone": "Asia/Taipei",
            "realms": [
                {
                    "id": 123,
                    "name": "Realm Name",
                    "slug": "realm-slug"
                },
                ...
            ]
        }
        """
        connected_realm = self.wrapper.get_connected_realm(region, crid)
        ret = {"id": crid, "realms": []}
        for realm in connected_realm["realms"]:
            if "timezone" in ret and ret["timezone"] != realm["timezone"]:
                raise ValueError(
                    "Timezone differes between realms under same connected realm!"
                )

            else:
                ret["timezone"] = realm["timezone"]

            ret["realms"].append(
                {
                    "id": realm["id"],
                    "name": realm["name"],
                    "slug": realm["slug"],
                    "locale": realm["locale"],
                }
            )

        return ret

    def pull_connected_realms(self, region: str) -> Any:
        """

        >>> {
                # connected realms
                $crid: $crid_data,
                ...
            }
        """
        crids = self.pull_connected_realms_ids(region)
        ret = {}
        for crid in crids:
            connected_realm = self.pull_connected_realm(region, crid)
            ret[crid] = connected_realm

        return ret

    def pull_commodities(self, region: str) -> Any:
        commodities = self.wrapper.get_commodities(region)
        return commodities

    def pull_auctions(self, region: str, crid: int) -> Any:
        auctions = self.wrapper.get_auctions(region, crid)
        return auctions

    def get_timezone(self, region: str, connected_realm_id: int) -> str:
        """NOTE: CRs under same region may have different timezones!"""
        connected_realm = self._api.get_connected_realm(region, connected_realm_id)
        return connected_realm["realms"][0]["timezone"]


class GHAPI(BoundCacheMixin):
    API_TEMPLATE = "https://api.github.com/repos/{user}/{repo}/releases/latest"

    def __init__(self, cache: Cache) -> None:
        super().__init__(cache=cache)

    @bound_cache(SECONDS_IN.HOUR)
    def get_assets_uri(self, owner: str, repo: str) -> Dict[str, str]:
        resp = requests.get(f"https://api.github.com/repos/{owner}/{repo}/releases")
        if resp.status_code != 200:
            raise ValueError(f"Failed to get releases: {resp.content}")
        releases = resp.json()
        ret = {}
        for asset in releases[0]["assets"]:
            ret[asset["name"]] = asset["browser_download_url"]

        return ret

    @bound_cache(SECONDS_IN.HOUR)
    def get_asset(self, url: str) -> bytes:
        resp = requests.get(url)
        if resp.status_code != 200:
            raise ValueError(f"Failed to get asset: {resp.content}")
        return resp.content
