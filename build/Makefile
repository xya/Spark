TARGETS = tarball archlinux

all: $(TARGETS)
	
tarball: 
	cd linux && make

archlinux: 
	cd archlinux && make

clean:
	cd linux && make clean
	cd archlinux && make clean
