#ifndef PYTHON_IOCP
#define PYTHON_IOCP

BOOL APIENTRY DllMain(HMODULE hModule,
                      DWORD  ul_reason_for_call,
                      LPVOID lpReserved);

PyMODINIT_FUNC init_iocp(void);
void iocp_win32error(const char *format);
BOOL iocp_createAsyncPipe(PHANDLE hRead, PHANDLE hWrite);

#endif