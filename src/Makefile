TARGET = sshpipe

all: $(TARGET)

$(TARGET): sshpipe.c
	gcc -o $@ -l ssh $<

clean:
	rm -f $(TARGET)
