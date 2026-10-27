CC ?= gcc
CFLAGS ?= -Wall -Wextra -std=c99 -O1 -I../Core/Inc

test: test_afe
	./test_afe

test_afe: test_afe.c ../Core/Src/afe.c
	$(CC) $(CFLAGS) -o $@ $^ -lm

clean:
	rm -f test_afe

.PHONY: test clean
