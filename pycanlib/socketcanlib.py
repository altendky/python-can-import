import ctypes
import socket
import sys

libc = ctypes.cdll.LoadLibrary("libc.so.6")

# Some of these constants are defined in the python socket library
CAN_RAW =       1
CAN_BCM =       2
PF_CAN  =       29
SOCK_RAW =      3
SOCK_DGRAM =    2
AF_CAN =        PF_CAN
SIOCGIFINDEX =  0x8933 
SIOCGSTAMP =    0x8906

start_sec = 0
start_usec = 0
SEC_USEC = 1000000

# See /usr/include/i386-linux-gnu/bits/socket.h for original struct
class SOCKADDR(ctypes.Structure):
    _fields_ = [("sa_family", ctypes.c_uint16),
                ("sa_data", (ctypes.c_char)*14) ]


# This struct is only used within the SOCKADDR_CAN struct
class TP(ctypes.Structure):
    _fields_ = [("rx_id", ctypes.c_uint32),
                ("tx_id", ctypes.c_uint32)]


# This struct is only used within the SOCKADDR_CAN struct
class ADDR_INFO(ctypes.Union):
    # This union is to future proof for future can address information
    _fields_ = [("tp", TP)]


# See /usr/include/linux/can.h for original struct
class SOCKADDR_CAN(ctypes.Structure):
    _fields_ = [("can_family", ctypes.c_uint16),
                ("can_ifindex", ctypes.c_int),
                ("can_addr", ADDR_INFO)]


# The two fields in this struct were originally unions.
# See /usr/include/net/if.h for original struct
class IFREQ(ctypes.Structure):
    _fields_ = [("ifr_name", (ctypes.c_char)*16),
                ("ifr_ifindex", ctypes.c_int)]


# See /usr/include/linux/can.h for original struct
#
# The data field actually only contains 8 bytes of data, not 11. 
# The linux socketcan module aligns the start of the data to an 8 byte 
# boundary, so there are 3 empty bytes between the DLC and the data. 
#
# I couldn't find a similar function in Python that did this, so am 
# saving the three empty bytes as part of the data, and getting rid 
# of them later. See the capturePacket function further down for this. 
class CAN_FRAME(ctypes.Structure):
    _fields_ = [("can_id", ctypes.c_uint32, 32),
                ("can_dlc", ctypes.c_uint8, 8),
                ("data", (ctypes.c_uint8)*11)]


# See usr/include/linux/time.h for original struct
class TIME_VALUE(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_ulong),
                ("tv_usec", ctypes.c_ulong)]


# Creates a CAN socket
#
# Socket can be BCM or RAW depending on input
# RAW socket needs to be bound
# BCM socket needs to be connected
# I am not sure how BCM sockets are used. 
#
# Returns:  0           if protocol is invalid
#           -1          if socket is not created successfully
#           socketID    if created successfully
def createSocket(canProtocol):
    if canProtocol == CAN_RAW:
        socketID = libc.socket(PF_CAN, SOCK_RAW, CAN_RAW)
    elif canProtocol == CAN_BCM:
        socketID = libc.socket(PF_CAN, SOCK_DGRAM, CAN_BCM)
    else:
        socketID = 0
    return socketID


# Binds a RAW CAN socket
#
# Returns:  0   if successful 
#           -1  if unsuccessful
def bindSocket(socketID):
    socketID = ctypes.c_int(socketID)
    
    ifr = IFREQ('can0')
    libc.ioctl(socketID, SIOCGIFINDEX, ctypes.byref(ifr))
    
    addr = SOCKADDR_CAN(AF_CAN, ifr.ifr_ifindex)
    
    # The size of addr struct is 72 in python, but 16 in C??? 
    error = libc.bind(socketID, ctypes.byref(addr), sys.getsizeof(addr))
    
    return error


# Captures a packet of CAN data from the socket specified.
#
# Returns:  A dictionary with the following fields:
#           CAN ID
#           DLC
#           Data
#           Timestamp
def capturePacket(socketID):
    
    packet = {}
    
    frame = CAN_FRAME()
    time = TIME_VALUE()
    
    # Fetching the Arb ID, DLC and Data
    bytesRead = libc.read(socketID, ctypes.byref(frame), sys.getsizeof(frame))
    
    # Fetching the timestamp
    error = libc.ioctl(socketID, SIOCGSTAMP, ctypes.byref(time));
    
    packet['CAN ID'] = frame.can_id
    packet['DLC'] = frame.can_dlc
    
    # The first 3 elements in the data array are discarded (as they are 
    # empty) and the rest (actual data) saved into a list. 
    data = []
    for i in range(3, frame.can_dlc + 3):
        data.append(frame.data[i])

    packet['Data'] = data
    
    
    global start_sec
    global start_usec
    
    if ( start_sec == 0) and ( start_usec == 0):
         start_sec = time.tv_sec;
         start_usec = time.tv_usec;
    
    timestamp = ((time.tv_usec - start_usec) + SEC_USEC*(time.tv_sec - start_sec))
    
    packet['Timestamp'] = timestamp

    return packet

