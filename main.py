# reMarkableSlidePDF - Kevin Wiesner
# ------------------------------------------------------ #
import io
import os
import uuid

from PyPDF2 import PdfFileWriter, PdfFileReader
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

# ------------------------------------------------------ #
# user settings

# file
DIRECTORY_TO_CONVERT = "./ToConvert/"
DIRECTORY_CONVERTED = "./Converted/"

# DIRECTORY_TO_CONVERT_UUID = "" - not relevant yet
DIRECTORY_CONVERTED_UUID = ""
REMARKABLE_XOCHITL_DIR = "/home/root/.local/share/remarkable/xochitl/"

FILEMODE = 0

# when FILEMODE = 0, specify directory to which the converted file should be saved
# when FILEMODE = 1, specify uuid4 of a reMarkable directory to which the converted file should be saved

# page
PAGE_SIZE = (223 * mm, 297 * mm)
SQUARE_SIZE = int(5 * mm)
DISPLAY_WIDTH = 205 * mm


# ------------------------------------------------------ #
# functions
def create_page_canvas(rect_size) -> io.BytesIO:
    # byte buffer
    new_packet = io.BytesIO()

    # new canvas
    c = canvas.Canvas(new_packet, pagesize=PAGE_SIZE)
    c.setStrokeGray(0.5)

    # draw vertical lines
    for y_line_pos in range(0, int(PAGE_SIZE[1]), SQUARE_SIZE):
        c.line(display_left_margin, y_line_pos, PAGE_SIZE[0], y_line_pos)

    # draw horizontal lines
    for x_line_pos in range(int(display_left_margin), int(PAGE_SIZE[0]), SQUARE_SIZE):
        c.line(x_line_pos, 0, x_line_pos, PAGE_SIZE[1])

    # setting for white background
    c.setFillGray(1)
    c.setStrokeGray(1)

    # draw white rect for transparent pdfs
    if rect_size[0] > rect_size[1]:  # Page in landscape format
        c.rect(display_left_margin, PAGE_SIZE[1] - rect_size[1], rect_size[0], rect_size[1], fill=1)
    else:  # Page in portrait format
        c.rect(display_left_margin, 0, rect_size[1], rect_size[0], fill=1)

    # save canvas
    c.save()

    return new_packet


# ------------------------------------------------------ #
# code

if __name__ == "__main__":
    display_left_margin = PAGE_SIZE[0] - DISPLAY_WIDTH

    directory = os.fsencode(DIRECTORY_TO_CONVERT)

    # loop over all files in specified directory
    for file in os.listdir(directory):
        filename = os.fsencode(file).decode("utf-8")
        if filename.endswith(".pdf"):  # only use .pdf files
            print("Converting", filename, "...")

            # open pdf and prepare output
            existing_pdf = PdfFileReader(open(DIRECTORY_TO_CONVERT + filename, "rb"))
            output = PdfFileWriter()

            # loop over every page of current pdf
            for page_number in range(existing_pdf.getNumPages()):
                modified_page = existing_pdf.getPage(page_number)
                size_modified = tuple(map(float, modified_page.mediaBox.upperRight))  # page size
                if size_modified[0] > size_modified[1]:  # Page in landscape format
                    rotation = 0
                    scale_factor = DISPLAY_WIDTH / size_modified[0]
                    x_pos = display_left_margin
                    y_pos = PAGE_SIZE[1] - (size_modified[1] * scale_factor)
                else:  # Page in portrait format
                    rotation = 90
                    scale_factor = DISPLAY_WIDTH / size_modified[1]
                    x_pos = PAGE_SIZE[0]
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
            if not FILEMODE:
                file_directory = DIRECTORY_CONVERTED + filename
            else:
                # generate uuid4 for the name of the pdf in the reMarkable filesystem (not visible name)
                file_uuid = str(uuid.uuid4())
                file_directory = REMARKABLE_XOCHITL_DIR + file_uuid + ".pdf"

                # create general content data
                with open(REMARKABLE_XOCHITL_DIR + file_uuid + ".content", "w") as content:
                    with open("./Templates/contentTemplate.json", "r") as contentTemplate:
                        content_to_write = contentTemplate.read()
                        content_to_write = content_to_write.replace("XX-PAGE-COUNT-XX", str(existing_pdf.getNumPages()))
                        content.write(content_to_write)

                # create general metadata for pdf
                with open(REMARKABLE_XOCHITL_DIR + file_uuid + ".metadata", "w") as metadata:
                    with open("./Templates/metadataTemplate.json", "r") as metadataTemplate:
                        metadata_to_write = metadataTemplate.read()
                        metadata_to_write = metadata_to_write.replace("XX-PARENT-XX", DIRECTORY_CONVERTED_UUID)
                        metadata_to_write = metadata_to_write.replace("XX-VISIBLE-FILENAME-XX", filename.replace(".pdf", ""))
                        metadata.write(metadata_to_write)

            # log the creation of the file (saving the directory)
            with open("./file-log.txt", "a") as log:
                extend_log = "\n" + file_directory
                log.write(extend_log)

            # save pdf
            output_stream = open(file_directory, "wb")
            output.write(output_stream)
            output_stream.close()
        else:
            print(filename, "is not a PDF")


# code END
# -------------------------------------------------
