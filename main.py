import fnmatch
import io
import json
import os
import uuid
import yaml

from PyPDF2 import PdfWriter, PdfReader, Transformation
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

# Function to load config from a YAML file
def load_config() -> dict:
    with open("config.yaml", "r") as ymlfile:
        return yaml.load(ymlfile, Loader=yaml.Loader)

# Function to create a canvas for a new page
def create_page_canvas(rect_size) -> io.BytesIO:
    new_packet = io.BytesIO()
    c = canvas.Canvas(new_packet, pagesize=page_size)
    c.setStrokeGray(0.5)

    # Drawing grid lines
    for y_line_pos in range(0, int(page_size[1]), square_size):
        c.line(display_left_margin, y_line_pos, page_size[0], y_line_pos)
    for x_line_pos in range(int(display_left_margin), int(page_size[0]), square_size):
        c.line(x_line_pos, 0, x_line_pos, page_size[1])

    # White background for transparent pdfs
    c.setFillGray(1)
    c.setStrokeGray(1)
    if rect_size[0] > rect_size[1]:  # Page in landscape format
        c.rect(display_left_margin, page_size[1] - rect_size[1], rect_size[0], rect_size[1], fill=1)
    else:  # Page in portrait format
        c.rect(display_left_margin, 0, rect_size[1], rect_size[0], fill=1)

    c.save()
    return new_packet

# Function to obtain files for conversion
def get_files(cfg, xochitl_directory):
    if os.path.isdir(xochitl_directory):
        for file in fnmatch.filter(os.listdir(xochitl_directory), "*.metadata"):
            with open(os.path.join(xochitl_directory, file), "r") as metadata_file:
                metadata = json.load(metadata_file)
                if metadata["parent"] == cfg["system"]["reMarkable"]["parent_to_convert"]:
                    visible_filename = metadata["visibleName"]
                    yield (os.path.join(xochitl_directory, file.replace(".metadata", ".pdf")), visible_filename)
    else:
        directory_to_convert = cfg["system"]["local"]["directory_to_convert"]
        for filename in fnmatch.filter(os.listdir(directory_to_convert), "*.pdf"):
            yield (os.path.join(directory_to_convert, filename), filename)


if __name__ == "__main__":
    cfg = load_config()

    page_size = (cfg["page"]["size"][0]*mm, cfg["page"]["size"][1]*mm)
    display_width = cfg["page"]["display_width"] * mm
    square_size = int(cfg["page"]["square_size"] * mm)
    display_left_margin = page_size[0] - display_width

    xochitl_directory = cfg["system"]["reMarkable"]["directory_to_convert"]

    files = get_files(cfg, xochitl_directory)

    # Processing PDF files
    for (filepath, visible_filename) in files:
        filename = os.path.basename(filepath)
        print("Converting", filename, "...")

        existing_pdf = PdfReader(open(filepath, "rb"))
        output = PdfWriter()

        for page_number in range(len(existing_pdf.pages)):
            modified_page = existing_pdf.pages[page_number]
            size_modified = tuple(map(float, modified_page.mediabox.upper_right))

            # Determine orientation and scaling
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

            # Create background
            packet = create_page_canvas(tuple(map(lambda dimension: dimension * scale_factor, size_modified)))
            squared_page = PdfReader(packet)
            size_squared = tuple(map(float, squared_page.pages[0].mediabox.upper_right))

            # Prepare pdf page for transformation
            new_width = max(size_modified[0], page_size[0])
            new_height = max(size_modified[1], page_size[1])
            modified_page.mediabox.upper_right = (new_width, new_height)

            # Merge background with pdf page
            page = squared_page.pages[0]
            modified_page.add_transformation(Transformation().rotate(rotation).scale(scale_factor).translate(x_pos, y_pos))
            page.merge_page(modified_page)
            page.compress_content_streams()
            output.add_page(page)

        # Write output pdf to specified directory
        if not os.path.isdir(xochitl_directory):
            file_directory = cfg["system"]["local"]["directory_converted"] + filename
        else:
            # Generate uuid4 for the name of the pdf in the reMarkable filesystem
            file_uuid = str(uuid.uuid4())
            file_directory = os.path.join(xochitl_directory, f"{file_uuid}.pdf")

            # Create general content data
            with open(os.path.join(xochitl_directory, f"{file_uuid}.content"), "w") as content:
                with open("./Templates/contentTemplate.json", "r") as content_template:
                    content_to_write = content_template.read().replace("XX-PAGE-COUNT-XX", str(existing_pdf.getNumPages()))
                    content.write(content_to_write)

            # Create general metadata for pdf
            with open(os.path.join(xochitl_directory, f"{file_uuid}.metadata"), "w") as metadata:
                with open("./Templates/metadataTemplate.json", "r") as metadata_template:
                    metadata_to_write = metadata_template.read().replace("XX-PARENT-XX", cfg["system"]["reMarkable"]["directory_converted"]).replace("XX-VISIBLE-FILENAME-XX", visible_filename)
                    metadata.write(metadata_to_write)

        # Log the creation of the file (saving the directory)
        with open("./file-log.txt", "a") as log:
            log.write(f"\n{file_directory}")

        # Save pdf
        with open(file_directory, "wb") as output_stream:
            output.write(output_stream)
    
    # Restart Xochitl to load the created files on the reMarkable
    if os.path.isdir(xochitl_directory) and cfg["system"]["reMarkable"]["execute_xochitl_restart"]:
        os.system("systemctl restart xochitl")
