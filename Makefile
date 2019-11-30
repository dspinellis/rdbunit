PREFIX?=/usr/local
EGTEST=simple datatypes

.PHONY: install
install: rdbunit.py
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	cp $< $(DESTDIR)$(PREFIX)/bin/rdbunit

.PHONY: uninstall
uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/rdbunit

postgresql-test:
	cd examples && ../rdbunit.py --database=postgresql *.rdbu | \
		psql -U ght -h 127.0.0.1 -t -q ghtorrent

mysql-test:
	cd examples && ../rdbunit.py *.rdbu | mysql -u root -p$$DBPASS -N

sqlite-test:
	cd examples && for i in *.rdbu ; do \
	  ../rdbunit.py --database=sqlite $$i | sqlite3 ; \
	done

qa:
	./runtest.sh python $(EGTEST)
	./runtest.sh python3 $(EGTEST)
	pycodestyle rdbunit.py
	pylint -r n rdbunit.py
