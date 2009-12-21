#ifndef PYTHON_IOCP
#define PYTHON_IOCP

BOOL APIENTRY DllMain(HMODULE hModule,
                      DWORD  ul_reason_for_call,
                      LPVOID lpReserved);

PyMODINIT_FUNC init_iocp(void);
void iocp_win32error(const char *format);
PyObject * iocp_createWinError(DWORD error, const char *format);
BOOL iocp_createAsyncPipe(PHANDLE hRead, PHANDLE hWrite);
void iocp_addConstant(PyObject *module, char *name, DWORD value);

// Type of operations handled by the completion port
#define OP_CLOSE        0
#define OP_INVOKE       1
#define OP_READ         2
#define OP_WRITE        3
#define OP_CONNECT      4
#define OP_ACCEPT       5

#endif