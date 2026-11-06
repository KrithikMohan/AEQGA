"""Prevent automatic system sleep only while the specified training process lives.

Does not change Windows power-plan settings or prevent explicit sleep/reboot.
The display remains free to turn off. The execution-state request ends on exit.
"""
import ctypes
from ctypes import wintypes
import sys


def main():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.SetThreadExecutionState.argtypes=[wintypes.DWORD]
    kernel.SetThreadExecutionState.restype=wintypes.DWORD
    process=kernel.OpenProcess(0x00100000,False,int(sys.argv[1]))
    if not process:raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel.SetThreadExecutionState(0x80000001):
            raise ctypes.WinError(ctypes.get_last_error())
        print('Automatic sleep prevented while training process is running.',flush=True)
        while True:
            result=kernel.WaitForSingleObject(process,30000)
            if result==0:break
            if result!=258:raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.SetThreadExecutionState(0x80000000)
        kernel.CloseHandle(process)
        print('Automatic sleep prevention released.',flush=True)


if __name__=='__main__':main()
