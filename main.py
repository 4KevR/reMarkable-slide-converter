# reMarkableSlidePDF - Kevin Wiesner
# ------------------------------------------------------ #
import fnmatch
import io
import json
import yaml
import os
import uuid

from PyPDF2 import PdfFileWriter, PdfFileReader
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


# ------------------------------------------------------ #
# functions
def load_config() -> dict:
    with open("config.yaml", "r") as ymlfile:
        return yaml.load(ymlfile, Loader=yaml.Loader)


def create_page_canvas(rect_size) -> io.BytesIO:
    # byte buffer
    new_packet = io.BytesIO()

    # new canvas
    c = canvas.Canvas(new_packet, pagesize=page_size)
    c.setStrokeGray(0.5)

    # draw vertical lines
    for y_line_pos in range(0, int(page_size[1]), square_size):
        c.line(display_left_margin, y_line_pos, page_size[0], y_line_pos)

    # draw horizontal lines
    for x_line_pos in range(int(display_left_margin), int(page_size[0]), square_size):
        c.line(x_line_pos, 0, x_line_pos, page_size[1])

    # setting for white background
    c.setFillGray(1)
    c.setStrokeGray(1)

    # draw white rect for transparent pdfs
    if rect_size[0] > rect_size[1]:  # Page in landscape format
        c.rect(display_left_margin, page_size[1] - rect_size[1], rect_size[0], rect_size[1], fill=1)
    else:  # Page in portrait format
        c.rect(display_left_margin, 0, rect_size[1], rect_size[0], fill=1)

    # save canvas
    c.save()

    return new_packet


# ------------------------------------------------------ #
# code

if __name__ == "__main__":
    cfg = load_config()

    page_size = (cfg["page"]["size"][0]*mm, cfg["page"]["size"][1]*mm)
    display_width = cfg["page"]["display_width"] * mm
    square_size = int(cfg["page"]["square_size"] * mm)

    display_left_margin = page_size[0] - display_width

    xochitl_directory = cfg["system"]["reMarkable"]["directory_to_convert"]
    system_config, filemode = (cfg["system"]["local"], 0) if not os.path.isdir(xochitl_directory)\
        else (cfg["system"]["reMarkable"], 1)

    if filemode:
        files = []
        for file in fnmatch.filter(os.listdir(xochitl_directory), "*.metadata"):
            with open(os.path.join(xochitl_directory, file), "r") as metadata_file:
                metadata = json.load(metadata_file)
                if metadata["parent"] == system_config["parent_to_convert"]:
                    visible_filename = metadata["visibleName"]
                    files.append((os.path.join(xochitl_directory, file.replace(".metadata", ".pdf")), visible_filename))
    else:
        files = list(map(lambda x: (x, x), fnmatch.filter(os.listdir(system_config["directory_to_convert"]), "*.pdf")))

    # loop over all pdf-files in specified directory
    for (file, visible_filename) in files:
        filename = os.path.basename(file)
        print("Converting", filename, "...")

        # open pdf and prepare output
        existing_pdf = PdfFileReader(open(os.path.join(system_config["directory_to_convert"], filename), "rb"))
        output = PdfFileWriter()

        # loop over every page of current pdf
        for page_number in range(existing_pdf.getNumPages()):
            modified_page = existing_pdf.getPage(page_number)
            size_modified = tuple(map(float, modified_page.mediaBox.upperRight))  # page size
            if size_modified[0] > size_modified[1]:  # Page in landscape format
                rotation = 0
                scale_factor = display_width / size_modified[0]
                x_pos = display_left_margin
                y_pos = page_size[1] - (size_modified[1] * scale_factor)
            else:  # Page in portrait format
                rotation = 90
                scale_factor = display_width / size_modified[1]
                x_pos = page_size[0]
                y_pos = 0

            # create background
            packet = create_page_canvas(tuple(map(lambda dimension: dimension * scale_factor, size_modified)))

            # open background in reader and get size of page
            squared_page = PdfFileReader(packet)
            size_squared = tuple(map(float, squared_page.getPage(0).mediaBox.upperRight))

            # merge background with pdf page
            page = squared_page.getPage(0)
            page.mergeRotatedScaledTranslatedPage(modified_page, rotation, scale_factor, x_pos, y_pos)
            page.compressContentStreams()
            output.addPage(page)

        # write output pdf to specified directory
        if not filemode:
            file_directory = system_config["directory_converted"] + filename
        else:
            # generate uuid4 for the name of the pdf in the reMarkable filesystem (not visible name)
            file_uuid = str(uuid.uuid4())
            file_directory = xochitl_directory + file_uuid + ".pdf"

            # create general content data
            with open(xochitl_directory + file_uuid + ".content", "w") as content:
                with open("./Templates/contentTemplate.json", "r") as contentTemplate:
                    content_to_write = contentTemplate.read()
                    content_to_write = content_to_write.replace("XX-PAGE-COUNT-XX", str(existing_pdf.getNumPages()))
                    content.write(content_to_write)

            # create general metadata for pdf
            with open(xochitl_directory + file_uuid + ".metadata", "w") as metadata:
                with open("./Templates/metadataTemplate.json", "r") as metadataTemplate:
                    metadata_to_write = metadataTemplate.read()
                    metadata_to_write = metadata_to_write.replace("XX-PARENT-XX", system_config["directory_converted"])
                    metadata_to_write = metadata_to_write.replace("XX-VISIBLE-FILENAME-XX", visible_filename)
                    metadata.write(metadata_to_write)

        # log the creation of the file (saving the directory)
        with open("./file-log.txt", "a") as log:
            extend_log = "\n" + file_directory
            log.write(extend_log)

        # save pdf
        output_stream = open(file_directory, "wb")
        output.write(output_stream)
        output_stream.close()

    if filemode and system_config["execute_xochitl_restart"]:
        os.system("systemctl restart xochitl")

# code END
# -------------------------------------------------
