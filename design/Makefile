TARGET = Specs.pdf
DIAGRAMS = Transfer.eps ProcessArch.eps View.eps

all: $(TARGET)

diagrams: $(DIAGRAMS)

%.pdf: %.tex
	pdflatex -halt-on-error $<

%.tex: %.lyx $(DIAGRAMS)
	lyx -e pdflatex $<

%.eps: %.dia
	dia -t eps-pango -e $@ $<

clean:
	rm -f *.log *.aux $(TARGET) *.eps *.tex
