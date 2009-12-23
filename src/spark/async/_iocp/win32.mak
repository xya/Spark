TARGET = ../_iocp.pyd
OBJECTS = iocp.obj CompletionPort.obj Future.obj AsyncFile.obj AsyncSocket.obj
PYTHOINCLUDE = C:\Python26\include
PYTHONLIBS = C:\Python26\libs

all: $(TARGET)

$(TARGET): $(OBJECTS)
	link /OUT:"$(TARGET)" /INCREMENTAL:NO /LIBPATH:"$(PYTHONLIBS)" /DLL /RELEASE /SUBSYSTEM:WINDOWS /MANIFEST:NO /OPT:REF /OPT:ICF /LTCG /DYNAMICBASE /NXCOMPAT /MACHINE:X86 /NOLOGO kernel32.lib ws2_32.lib $(OBJECTS)
	
.cpp.obj:
	cl /I $(PYTHOINCLUDE) /O2 /Oi /GL  /D "WIN32" /D "NDEBUG" /D "_WINDOWS" /D "_USRDLL" /D "_WINDLL" /D "_UNICODE" /D "UNICODE" /FD /MD /W3 /c /TC /GR- /nologo $*.cpp
