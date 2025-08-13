import asyncio
from bleak import BleakScanner, BleakClient

TARGET_NAME = "GVH5104"  # Govee H5104 device name pattern

async def main():
    print("🔍 Scanning for a Govee H5104 thermometer and connecting...")

    # Keep scanning until we find one
    device = None
    while device is None:
        devices = await BleakScanner.discover(timeout=3)
        for dev in devices:
            if dev.name and TARGET_NAME in dev.name:
                device = dev
                break

    print(f"✅ Found {device.name} | Address: {device.address}")
    
    # Connect immediately after finding it
    try:
        async with BleakClient(device.address, timeout=15.0) as client:
            if client.is_connected:
                print(f"✅ Connected to {device.address}")
            else:
                print(f"❌ Failed to connect to {device.address}")
                return

            # In Bleak 1.0+, services are auto-fetched after connect
            services = client.services

            for service in services:
                print(f"[Service] {service.uuid} ({service.description})")
                for char in service.characteristics:
                    props = ",".join(char.properties)
                    print(f"  └─ [Characteristic] {char.uuid} ({props})")

    except Exception as e:
        print(f"⚠️ Error connecting to {device.address}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
