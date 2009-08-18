TARGET = Specs.pdf
DIAGRAMS = Transfer.png

all: $(TARGET)

%.pdf: %.tex
	pdflatex -halt-on-error $<

%.tex: %.lyx $(DIAGRAMS)
	lyx -e pdflatex $<

%.png: %.dia
	dia -t png-libart -e $@ $<

clean:
	rm -f *.log *.aux $(TARGET) *.png *.tex