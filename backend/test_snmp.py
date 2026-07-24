import asyncio

from pysnmp.hlapi.v3arch.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    get_cmd,
)


async def main():
    target_ip = "192.168.24.168"
    community = "public"

    print(f"Testing SNMP on {target_ip}...")

    error_indication, error_status, error_index, var_binds = await get_cmd(
        SnmpEngine(),
        CommunityData(community, mpModel=1),
        await UdpTransportTarget.create(
            (target_ip, 161),
            timeout=3,
            retries=1,
        ),
        ContextData(),
        ObjectType(
            ObjectIdentity(
                "1.3.6.1.2.1.1.1.0"
            )
        ),
    )

    if error_indication:
        print("❌ SNMP FAILED")
        print(error_indication)
        return

    if error_status:
        print("❌ SNMP ERROR")
        print(error_status.prettyPrint())
        return

    print("✅ SNMP SUCCESS")

    for var_bind in var_binds:
        print(var_bind)


if __name__ == "__main__":
    asyncio.run(main())