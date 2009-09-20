TARGET = sshpipe
OBJECTS = common.o client.o server.o

all: $(TARGET)
	
$(TARGET): $(OBJECTS)
	gcc -o $@ -l ssh $(OBJECTS)

%.o: %.c
	gcc -c -o $@ $<

clean:
	rm -f $(TARGET) $(OBJECTS)
