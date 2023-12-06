import hashlib
import base64
import panflute as pf
import re
import os
import yaml
from datetime import date as datetime_date



# Globaler Cache
parsed_files_cache = {}
citations_db = {}
replace_cit = None

def md5_hash(string, length=15):
    # Generiere den MD5 Hash
    hash_object = hashlib.md5(string.encode('utf-8'))
    # Konvertiere den Hash in einen Base64-String
    base64_string = base64.b64encode(hash_object.digest()).decode('utf-8')
    # Entferne alle Zahlen und Sonderzeichen
    letters_only = re.sub(r'[^A-Za-z]+', '', base64_string)
    # Kürze den String auf die gewünschte Länge
    return letters_only[:length]

def escape_latex(s):
    replacements = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
        '\\': r'\textbackslash{}',
        '\n': r'\\',  # Newline char to LaTeX newline command
        ' ': r'~',  # Non-breaking space (narrow)
        ' ': r'~'   # Non-breaking space (regular)
    }
    for original, replacement in replacements.items():
        s = s.replace(original, replacement)
    return s



def add_to_citations_db(citation_info, prefix='', postfix=''):
    global citations_db
    # Escape LaTeX special characters

    hash_key = md5_hash(f"{prefix} {citation_info} {postfix}")
    if hash_key not in citations_db:
        if postfix:
            postfix = ", " + postfix
        
        if prefix:
            prefix = prefix + " "
        
        citation_info = escape_latex(citation_info)
        prefix = escape_latex(prefix)
        postfix = escape_latex(postfix)
        
        formatted_citation = f"\n"
        # Fußnoten spezifischen Fußnotenzähler definieren und initialisieren
        formatted_citation += f"\\newcounter{{fn{hash_key}}}\n"
        formatted_citation += f"\\setcounter{{fn{hash_key}}}{{0}}\n"
        
        # Fußnoten spezifischen Labelzähler definieren und initialisieren
        formatted_citation += f"\\newcounter{{lb{hash_key}}}\n"
        formatted_citation += f"\\setcounter{{lb{hash_key}}}{{0}}\n"
        
        # Fußnoten spezifischen Seitenzähler definieren und initialisieren
        formatted_citation += f"\\newcounter{{pg{hash_key}}}\n"
        formatted_citation += f"\\setcounter{{pg{hash_key}}}{{0}}\n"
        
        formatted_citation += (f'\\newcommand{{\{hash_key}}}{{%\n'
                               f' \\label{{{hash_key}\\thelb{hash_key}}}%\n'
                               f' \\setconditionalpageref{{{hash_key}\\thelb{hash_key}}}%\n'
                               f' \\ifnum\\value{{pg{hash_key}}}=\\value{{conditionalPageRef}}%\n'
                               f'  \\hyperlink{{tg{hash_key}\\thefn{hash_key}}}{{\\footnotemark[\\thefn{hash_key}]{{}}}}%\n'
                               f' \else%\n'
                               f'  \stepcounter{{footnote}}%\n'
                               f'  \setcounter{{pg{hash_key}}}{{\\value{{conditionalPageRef}}}}%\n'
                               f'  \setcounter{{fn{hash_key}}}{{\\thefootnote}}%\n'
                               f'  \\footnotetext[\\thefootnote]{{\\vadjust pre{{\\hypertarget{{tg{hash_key}\\thefn{hash_key}}}{{}}}}{prefix}{citation_info}{postfix}}}%\n'
                               f'  \\hyperlink{{tg{hash_key}\\thefn{hash_key}}}{{\\footnotemark[\\thefn{hash_key}]{{}}}}%\n'
                               f' \\fi%\n'
                               f' \\stepcounter{{lb{hash_key}}}%\n'
                               f'}}%\n')

        formatted_citation = "\n".join(line.lstrip() for line in formatted_citation.splitlines())
        
        citations_db[hash_key] = formatted_citation
    return hash_key


    
def output_citations(doc):
    citations_str = ''.join(citations_db.values())
    doc.metadata['citations-in-preamble'] = pf.MetaInlines(pf.RawInline(citations_str, format='latex'))

    return doc


def get_metadata_file_path(file_name):
    base_path = "C:\\Users\\maxim\\Cloud\\Projekte\\Referenzen\\Metadaten"
    file_path = os.path.join(base_path, file_name + '.md')
    return file_path

def parse_document(file_path):
    # Verwenden Sie den globalen Cache
    global parsed_files_cache

    # Überprüfen, ob die Datei bereits geparsed wurde
    if file_path in parsed_files_cache:
        return parsed_files_cache[file_path]

    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # Extrahiere den YAML-Header
    yaml_header_str = re.search(r'^---(.*?)---', content, re.DOTALL)
    yaml_header = None
    markdown_content = content

    if yaml_header_str:
        yaml_header = yaml.safe_load(yaml_header_str.group(1))
        markdown_content = content[yaml_header_str.end():]  # Der Rest des Inhalts nach dem YAML-Header

    # Suche nach dem TAGS-Abschnitt und extrahiere Tags und das dazugehörige Target
    tags_targets = re.findall(r'^>%%TAGS%%\n(.*?)\n(\^.*?)\n', markdown_content, re.MULTILINE | re.DOTALL)
    
    tags_targets_dict = {}

    for tags, target in tags_targets:
        # Entferne führende `>` Zeichen und splitte die Tags bei Kommas
        tag_list = [tag.strip() for tag in tags.split(',')]
        # Zuordnung des ersten Tags, der mit '##' beginnt, zum Target
        if tag_list:
            # Entferne das '##' und das abschließende Komma, falls vorhanden
            clean_tag = tag_list[0].replace('##', '').replace('>', '').rstrip(',')
            tags_targets_dict[target.strip()] = clean_tag

    # Speichern der Ergebnisse im Cache
    parsed_files_cache[file_path] = (yaml_header, tags_targets_dict)

    return yaml_header, tags_targets_dict


def construct_citation(parsed_yaml):
    # Versuche, das Feld 'citationTitle' zu holen
    citation_title = parsed_yaml.get('citationTitle')
    if citation_title:
        return citation_title

    # Ansonsten setze die Felder 'date', 'title' und 'sender' zusammen
    date_obj = parsed_yaml.get('date', None)
    # Überprüfe, ob 'date' ein datetime.date-Objekt ist und konvertiere es zu einem String
    if isinstance(date_obj, datetime_date):
        date = date_obj.strftime('%Y.%m.%d')
    else:
        date = ''

    title = parsed_yaml.get('title', '')
    sender = parsed_yaml.get('sender', '')

    # Stelle sicher, dass alle Informationen vorhanden sind
    if not all([date, title, sender]):
        return "Unvollständige Zitatinformationen"

    # Formatierung des Zitatstrings
    return f"{date} - von {sender} - {title}"

def write_to_file(content, file_path):
    with open(file_path, 'a', encoding='utf-8') as file:
        file.write(content + '\n')

#elem.url = URL
#elem.content = TEXT

def parse_wikilinks(elem, doc):
    global replace_cit
    if isinstance(elem, pf.Link) and elem.title == 'wikilink':
        container = []
        link_text = pf.stringify(elem.content)
        link_url = elem.url
    
        if link_text != "^" and link_text != "°":
            text = pf.convert_text(pf.stringify(elem.content), input_format="markdown")
            for element in text:
                if isinstance(element, pf.Para):
                    for inner_element in element.content:
                        container.append(inner_element)  # Füge nur den Inhalt des Para-Elements hinzu
                else:
                    #container.append(element)
                    pass
        else:
            text = None
        
        
        url_pattern = re.compile(r'(.*?)#(\^\w*)')
        url_match = url_pattern.search(link_url)
        
        if url_match:
            file = url_match.group(1)
            target = url_match.group(2)
        else:
            return elem
        
        
        metadata_file_path = get_metadata_file_path(file)
        if os.path.isfile(metadata_file_path):
            # Parsen von YAML-Header und Markdown-Tags
            yaml_header, tags_targets_dict = parse_document(metadata_file_path)

            if yaml_header:
                # Konstruiere Zitat-Informationen aus YAML-Header
                citation_info = construct_citation(yaml_header)
            else:
                return elem

            # Finde die entsprechenden Tags für das Target
            citation_tag = tags_targets_dict.get(target, None)

            # Erstelle den Debug-Text einschließlich des tags_targets_dict
            if text != None:
                if citation_tag != None:
                    hash_key = add_to_citations_db(citation_info, postfix=citation_tag)
                else:
                    hash_key = add_to_citations_db(citation_info)
                   
                latex = f'\\{hash_key}{{}}'
                replace_cit = pf.RawInline(latex, format='latex')
                return container
                
            else:
                if citation_tag != None:
                    hash_key = add_to_citations_db(citation_info, "vgl.", citation_tag)
                else:
                    hash_key = add_to_citations_db(citation_info, prefix="vgl.")
                
                latex = f'\\{hash_key}{{}}'
                return [pf.RawInline(latex, format='latex')]
        else:
            return elem
    elif replace_cit != None and isinstance(elem, pf.Str) and elem.text.startswith("“"):
        container = []
        
        text = elem.text
        quote_mark = text[0]
        remaining_text = text[1:]
        
        container.append(pf.Str(quote_mark))
        container.append(replace_cit)
        container.append(pf.Str(remaining_text))

        replace_cit = None
        return container
    
    return elem

def wrap_paragraphs_in_samepage(elem, doc):
    if isinstance(elem, pf.Para):
        #write_to_file(f"Para: {elem}", "C:\\Users\\maxim\\Working\\debug.txt")
        # Überprüfen, ob eines der Kinder ein RawInline-Element ist und den Key enthält
        for child in elem.content:
            if isinstance(child, pf.RawInline) and any(key in child.text for key in citations_db):
                # Erstelle einen neuen Container für den Absatz
                new_content = [pf.RawInline('\\begin{samepage}', format='latex')]
                new_content.extend(elem.content)
                new_content.append(pf.RawInline('\par\\end{samepage}', format='latex'))

                # Ersetze den ursprünglichen Absatz mit dem neuen Inhalt
                return pf.Para(*new_content)
    return elem

def main(doc=None):
    # Leere die Debug-Datei zu Beginn
    #open("C:\\Users\\maxim\\Working\\debug.txt", 'w').close()

    doc = pf.load()
    doc = pf.run_filter(parse_wikilinks, doc=doc)
    #doc = pf.run_filter(wrap_paragraphs_in_samepage, doc=doc)
    doc = output_citations(doc)
    pf.dump(doc)

if __name__ == '__main__':
    main()