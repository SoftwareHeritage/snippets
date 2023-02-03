
# Optical patch panels
# SIDE_A_DEVICES=["C11-1-optical", "C11-2-optical", "C12-1-optical", "C12-2-optical"]
# SIDE_B_DEVICES=["C11-1-optical-arrival", "C11-2-optical-arrival", "C12-1-optical-arrival", "C12-2-optical-arrival"]
# PORT_PREFIX="snapin-rear"
# CABLE_TYPE="mmf-om3"

# Management Ethernet patch panels
SIDE_A_DEVICES=["C11-eth-management", "C12-eth-management"]
SIDE_B_DEVICES=["C11-eth-management-arrival", "C12-eth-management-arrival"]
PORT_PREFIX="trunk"
CABLE_TYPE="cat6a"

STATUS="connected"
PORT_TYPE="dcim.rearport"
PORT_COUNT=24

print("side_a_device,side_a_type,side_a_name,side_b_device,side_b_type,side_b_name,type,status")

for (i, side_a_device) in enumerate(SIDE_A_DEVICES):
  side_b_device = SIDE_B_DEVICES[i]
  for port_num in range(1,PORT_COUNT+1):
    port = f"{PORT_PREFIX}{port_num}"
    print(f"{side_a_device},{PORT_TYPE},{port},{side_b_device},{PORT_TYPE},{port},{CABLE_TYPE},{STATUS}")

