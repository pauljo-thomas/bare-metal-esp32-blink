PROJECT := blink
BUILD := build
TOOLCHAIN ?= $(CURDIR)/xtensa-esp32-elf/bin
AS := $(TOOLCHAIN)/xtensa-esp32-elf-as
OBJDUMP := $(TOOLCHAIN)/xtensa-esp32-elf-objdump
READELF := $(TOOLCHAIN)/xtensa-esp32-elf-readelf
PYTHON ?= python3
PORT ?= /dev/ttyUSB0

.PHONY: all clean inspect flash
all: $(BUILD)/$(PROJECT).bin

$(BUILD):
	mkdir -p $@

$(BUILD)/$(PROJECT).o: firmware.S | $(BUILD)
	$(AS) -o $@ $<

$(BUILD)/$(PROJECT).raw $(BUILD)/$(PROJECT).json: $(BUILD)/$(PROJECT).o tools/layout.py
	$(PYTHON) tools/layout.py $< $(BUILD)/$(PROJECT).raw $(BUILD)/$(PROJECT).json --load-address 0x40080000

$(BUILD)/$(PROJECT).bin: $(BUILD)/$(PROJECT).raw $(BUILD)/$(PROJECT).json tools/pack_image.py
	$(PYTHON) tools/pack_image.py $(BUILD)/$(PROJECT).raw $(BUILD)/$(PROJECT).json $@

inspect: $(BUILD)/$(PROJECT).o $(BUILD)/$(PROJECT).bin
	$(READELF) -r $(BUILD)/$(PROJECT).o
	$(OBJDUMP) -d $(BUILD)/$(PROJECT).o
	$(PYTHON) tools/inspect_image.py $(BUILD)/$(PROJECT).bin

flash: $(BUILD)/$(PROJECT).bin
	$(PYTHON) tools/rom_flash.py --port $(PORT) $< 0x1000

clean:
	rm -rf $(BUILD)
