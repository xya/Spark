TARGET = sshpipe
OBJECTS = common.o client.o server.o

all: $(TARGET)
	
$(TARGET): $(OBJECTS)
	gcc -o $@ -l ssh -ggdb $(OBJECTS)

%.o: %.c
	gcc -c  -ggdb -o $@ $<

clean:
	rm -f $(TARGET) $(OBJECTS)
