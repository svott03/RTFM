import fitz
from operator import itemgetter
import openai
import time
import backoff


def isclose(a, b, rel_tol=1e-09, abs_tol=0.0):
    return abs(a-b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


def fonts(doc, granularity=False):
    """Extracts fonts and their usage in PDF documents.
    :param doc: PDF document to iterate through
    :type doc: <class 'fitz.fitz.Document'>
    :param granularity: also use 'font', 'flags' and 'color' to discriminate text
    :type granularity: bool
    :rtype: [(font_size, count), (font_size, count}], dict
    :return: most used fonts sorted by count, font style information
    """
    styles = {}
    font_counts = {}

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:  # iterate through the text blocks
            if b['type'] == 0:  # block contains text
                for l in b["lines"]:  # iterate through the text lines
                    for s in l["spans"]:  # iterate through the text spans
                        if granularity:
                            identifier = "{0}_{1}_{2}_{3}".format(
                                s['size'], s['flags'], s['font'], s['color'])
                            styles[identifier] = {'size': s['size'], 'flags': s['flags'], 'font': s['font'],
                                                  'color': s['color']}
                        else:
                            identifier = "{0}".format(s['size'])
                            styles[identifier] = {
                                'size': s['size'], 'font': s['font']}

                        font_counts[identifier] = font_counts.get(
                            identifier, 0) + 1  # count the fonts usage

    font_counts = sorted(font_counts.items(), key=itemgetter(1), reverse=True)

    if len(font_counts) < 1:
        raise ValueError("Zero discriminating fonts found!")

    return font_counts, styles


def font_tags(font_counts, styles):
    """Returns dictionary with font sizes as keys and tags as value.
    :param font_counts: (font_size, count) for all fonts occuring in document
    :type font_counts: list
    :param styles: all styles found in the document
    :type styles: dict
    :rtype: dict
    :return: all element tags based on font-sizes
    """
    p_style = styles[font_counts[0][0]
                     ]  # get style for most used font by count (paragraph)
    p_size = p_style['size']  # get the paragraph's size

    # sorting the font sizes high to low, so that we can append the right integer to each tag
    font_sizes = []
    for (font_size, count) in font_counts:
        font_sizes.append(float(font_size))
    font_sizes.sort(reverse=True)

    # aggregating the tags for each font size
    idx = 0
    size_tag = {}
    for size in font_sizes:
        idx += 1
        if size == p_size:
            idx = 0
            size_tag[size] = '<p>'
        if size > p_size:
            size_tag[size] = '<h{0}>'.format(idx)
        elif size < p_size:
            size_tag[size] = '<s{0}>'.format(idx)

    return size_tag


def headers_para(doc, size_tag, font_counts):
    """Scrapes headers & paragraphs from PDF and return texts with element tags.
    :param doc: PDF document to iterate through
    :type doc: <class 'fitz.fitz.Document'>
    :param size_tag: textual element tags for each size
    :type size_tag: dict
    :rtype: list
    :return: texts with pre-prended element tags
    """
    header_para = []  # list with headers and paragraphs
    first = True  # boolean operator for first header
    previous_s = {}  # previous span
    reduce_fonts = {}

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:  # iterate through the text blocks
            if b['type'] == 0:  # this block contains text

                # REMEMBER: multiple fonts and sizes are possible IN one block

                block_string = ""  # text found in block
                for l in b["lines"]:  # iterate through the text lines
                    for s in l["spans"]:  # iterate through the text spans
                        if s['text'].strip():  # removing whitespaces:
                            if first:
                                previous_s = s
                                first = False
                                block_string = size_tag[s['size']] + s['text']
                            else:
                                if s['size'] == previous_s['size']:
                                    if block_string and all((c == "|") for c in block_string):
                                        # block_string only contains pipes
                                        block_string = size_tag[s['size']
                                                                ] + s['text']
                                    elif block_string == "":
                                        # new block has started, so append size tag
                                        block_string = size_tag[s['size']
                                                                ] + s['text']
                                    else:  # in the same block, so concatenate strings
                                        block_string += " " + s['text']
                                        if (str(s['size']) in reduce_fonts):
                                            reduce_fonts[str(s['size'])] += 1
                                        else:
                                            reduce_fonts[str(s['size'])] = 1

                                else:
                                    header_para.append(block_string)
                                    block_string = size_tag[s['size']
                                                            ] + s['text']

                                previous_s = s

                    # new block started, indicating with a pipe
                    block_string += "|"

                header_para.append(block_string)
    for index, elem in enumerate(font_counts):
        if (elem[0] in reduce_fonts):
            font_counts[index] = (font_counts[index][0],
                                  font_counts[index][1] - reduce_fonts[elem[0]])
    return header_para


def find_subheading(font_counts, size_tag):
    headers = []
    for font_size, count in font_counts:
        if ('h' in size_tag[float(font_size)]):
            headers.append((size_tag[float(font_size)], count))

    headers = sorted(headers, key=itemgetter(1), reverse=True)
    return headers


def grab_chunks(text_bodies, header, result, tag_index):
    spots = []
    for heading, index in tag_index:
        if (heading == header):
            spots.append(index)
    # spots = [0, 6, 20 ...] where spots[i] is an entry in result that starts with header
    i = 0
    for index, elem in enumerate(spots):
        if (index == (len(spots) - 1)):
            break
        first_index = elem
        second_index = spots[index+1]
        chunk = result[first_index: second_index]
        # concat
        chunk_string = ' '.join(map(str, chunk))
        # TODO parse out chunks of size less than 50words * 4 chars = 200 chars ?
        if (len(chunk_string) > 200):
            text_bodies.append(chunk_string)
    last_chunk = result[spots[len(spots) - 1]:]
    last_chunk_string = ' '.join(map(str, last_chunk))
    # May not want to include this string
    text_bodies.append(last_chunk_string)


# @backoff.on_exception(backoff.expo, openai.error.RateLimitError)
# def completions_with_backoff(**kwargs):
#     return openai.Completion.create(**kwargs)


# completions_with_backoff(model="text-davinci-003", prompt="Once upon a time,")


def send_prompts(acceptable_templates, headers_used, outputs):
    st = time.time()
    # Right now, simply output the first 10 for <h2>
    t = 0
    for index, elem in enumerate(acceptable_templates):
        if (t == 0):
            t += 1
            continue
        print("On header", headers_used[index])
        print("We have ", len(elem), "text chunks")
        print("Querying GPT")
        cur_output = []
        for i, chunk in enumerate(elem):
            if (i == 3):
                break

            print("On Chunk", i, "-------------")
            # Catching exceptions (timeout, remote disconnection, bad gateway)

            # token limit
            if (len(chunk) > (4097 - 1080)):
                for k in range(0, len(chunk), 4097-1080):
                    inference_not_done = True
                    while (inference_not_done):
                        try:
                            prompt = "I will give you a page of hardware documentation from an electric engineering manual. I want you to make some new documentation inspired by software documentation's simple and relatively easy to read layout."
                            prompt += "\n" + \
                                chunk[k:min(len(chunk), k + (4097-1080))]
                            completion = openai.ChatCompletion.create(
                                model="gpt-3.5-turbo",
                                messages=[{"role": "user", "content": prompt}],
                                max_tokens=1024,
                                temperature=0.8)
                            cur_output.append(completion)
                            inference_not_done = False
                        except Exception as e:
                            print(f"Waiting 5 minutes")
                            print(f"Error was: {e}")
                            time.sleep(300)
            else:
                inference_not_done = True
                while (inference_not_done):
                    try:
                        prompt = "I will give you a page of hardware documentation from an electric engineering manual. I want you to make some new documentation inspired by software documentation's simple and relatively easy to read layout."
                        prompt += "\n" + chunk
                        completion = openai.ChatCompletion.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=1024,
                            temperature=0.8)
                        cur_output.append(completion)
                        inference_not_done = False
                        # print(completion)
                    except Exception as e:
                        print(f"Waiting 5 minutes")
                        print(f"Error was: {e}")
                        time.sleep(300)
        outputs.append(cur_output)
    et = time.time()
    elapsed_time = et - st
    print('Execution time:', elapsed_time, 'seconds')


def parse_documention(document):
    # doc = fitz.open('Oscilloscope.pdf')
    doc = fitz.open(document)
    font_counts, styles = fonts(doc, granularity=False)
    size_tag = font_tags(font_counts, styles)
    result = headers_para(doc, size_tag, font_counts)
    headers = find_subheading(font_counts, size_tag)
    tag_index = []

    for index, chunk in enumerate(result):
        if (len(chunk) > 0):
            if chunk[0] == "<":
                tag_index.append((chunk[:chunk.find('>') + 1], index))

    page_count = len(doc)
    acceptable_templates = []

    # We can output based on <h5>, <h7> is the most popular <h346> are negligible, <h2> is nice
    headers_used = []

    print("PAGE COUNT", page_count)
    for header, count in headers:
        # accept headers if 10% of pages <= count <= 2 * pages
        if (count >= int(page_count/10) and count <= 1.5 * page_count):
            text_bodies = []
            # grab chunks of text for page_count
            grab_chunks(text_bodies, header, result, tag_index)
            acceptable_templates.append(text_bodies)
            headers_used.append(header)

    print("Headers used:", headers_used)
    outputs = []
    send_prompts(acceptable_templates, headers_used, outputs)

    print('Here are the outputs for <h2>')
    result = []
    for i in range(0, len(outputs[0])):
        print('Chunk', i, '------------------------------------------------')
        print(outputs[0][i]['choices'][0]['message']['content'])
    
    return result
