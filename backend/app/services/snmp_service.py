import logging
from typing import Any, Dict

from pysnmp.hlapi.v3arch.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    get_cmd,
)


logger = logging.getLogger(__name__)


class SNMPService:

    def __init__(
        self,
        community: str = "public",
        port: int = 161,
        timeout: int = 2,
        retries: int = 1,
    ):

        self.community = community
        self.port = port
        self.timeout = timeout
        self.retries = retries

    async def get_system_info(
        self,
        ip_address: str,
    ) -> Dict[str, Any]:

        ip_address = str(ip_address)

        try:

            logger.info(
                f"📡 SNMP polling {ip_address}"
            )

            transport = (
                await UdpTransportTarget.create(
                    (
                        ip_address,
                        self.port,
                    ),
                    timeout=self.timeout,
                    retries=self.retries,
                )
            )

            error_indication, error_status, error_index, var_binds = (
                await get_cmd(
                    SnmpEngine(),

                    CommunityData(
                        self.community,
                        mpModel=1,
                    ),

                    transport,

                    ContextData(),

                    ObjectType(
                        ObjectIdentity(
                            "SNMPv2-MIB",
                            "sysName",
                            0,
                        )
                    ),

                    ObjectType(
                        ObjectIdentity(
                            "SNMPv2-MIB",
                            "sysDescr",
                            0,
                        )
                    ),

                    ObjectType(
                        ObjectIdentity(
                            "SNMPv2-MIB",
                            "sysUpTime",
                            0,
                        )
                    ),
                )
            )

            if error_indication:

                logger.error(
                    f"❌ SNMP error for "
                    f"{ip_address}: "
                    f"{error_indication}"
                )

                return {
                    "success":
                        False,

                    "ip_address":
                        ip_address,

                    "error":
                        str(error_indication),
                }

            if error_status:

                error_message = (
                    f"{error_status.prettyPrint()} "
                    f"at index "
                    f"{error_index}"
                )

                logger.error(
                    f"❌ SNMP error for "
                    f"{ip_address}: "
                    f"{error_message}"
                )

                return {
                    "success":
                        False,

                    "ip_address":
                        ip_address,

                    "error":
                        error_message,
                }

            system_info = {}

            for oid, value in var_binds:

                oid_string = (
                    oid.prettyPrint()
                )

                value_string = (
                    value.prettyPrint()
                )

                system_info[
                    oid_string
                ] = value_string

            logger.info(
                f"✅ SNMP poll successful "
                f"for {ip_address}"
            )

            return {
                "success":
                    True,

                "ip_address":
                    ip_address,

                "system_info":
                    system_info,
            }

        except Exception as exc:

            logger.error(
                f"❌ SNMP polling error "
                f"for {ip_address}: {exc}",
                exc_info=True,
            )

            return {
                "success":
                    False,

                "ip_address":
                    ip_address,

                "error":
                    str(exc),
            }