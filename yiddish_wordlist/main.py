#!/usr/bin/env python3

import string
import re
import json
import argparse
import numpy as np
import os.path as op
from wiktionaryparser import WiktionaryParser
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup


def wiktionary_definition(wordlist):
    """Get definition for wordlist from Wiktionary.

    Parameters
    ----------
    wordlist : dict
        Dictionary whose keys are words to check from wiktionary. Values are
        ignored.

    Returns
    -------
    wordlist : dict
        The input dictionary, with a wiktionary entry added (entry is a list of
        dictionaries)

    """
    parser = WiktionaryParser()
    parser.set_default_language('Yiddish')
    parser.include_relation('derived terms')
    parser.include_relation('alternative forms')
    parser.include_relation('see also')
    for word, defs in wordlist.items():
        print(f'Looking up {word} from Wiktionary')
        wikt = parser.fetch(word)
        for wi in wikt:
            wi['transliteration'] = []
            # remove the audio, which is never there anyway
            wi['pronunciations'] = wi['pronunciations']['text']
            for defi in wi['definitions']:
                txt = defi.pop('text')
                defi['text'] = txt[1:]
                txt = txt[0]
                defi['lexeme'] = txt.split('•')[0].strip()
                wi['transliteration'].append(txt.split('•')[1].split(')')[0].replace('(', '').strip())
                if u'\xa0' in txt:
                    defi['gender'] = txt.split(u'\xa0')[1].split(',')[0]
                else:
                    defi['gender'] = None
                if 'plural' in txt:
                    defi['plural'] = txt.split('plural')[1].strip()
                else:
                    defi['plural'] = None
                if 'participle' in txt:
                    defi['participle'] = txt.split('participle')[1].replace('))', ')').strip()
                else:
                    defi['participle'] = None
            if len(set(wi['transliteration'])) == 1:
                wi['transliteration'] = wi['transliteration'][0]
        wordlist[word]['wiktionary'] = wikt
    return wordlist


def _get_word_from_kentucky(browser, word):
    """Construct dictionary with definition for a single word.

    when finding a match:
    - it will be a span/goodmatch
    - can't assume it will be the first / last / anything
    - can't assume it will be on the outside list
    - can't assume it will be the only word in the span
    - entry will be have the stem in the lexeme, if there are multiple, take all.
    - if there isn't an entry there the stem is in the lexeme: take all goodmatches

    Parameters
    ----------
    browser : selenium.webdriver
        Browser opened to the Kentucky Yiddish dictionary page.
    word : str
        Word to get the definition for

    Returns
    -------
    definition : dict
        Dictionary containing all info scraped from the dictionary.

    """
    print(f'Looking up {word} from the Kentucky dictionary')
    browser.find_element('name', 'base').send_keys(word + Keys.RETURN)
    soup = BeautifulSoup(browser.page_source, 'html.parser')
    # Get transliteration
    transl = soup.find('span', 'grammar')
    assert soup.find(string='Converting ') == transl.previous_sibling.previous_sibling.previous_sibling, "Can't find transliteration!"
    stem = soup.find('span', 'goodmatch')
    assert soup.find(string='\nThe base word for ') == stem.previous_sibling.previous_sibling.previous_sibling, "Can't find transliteration!"
    ky = {'transliteration': transl.text, 'stem': stem.text}
    # azoy words[11] has many examples, which I'd like -- they're all in the
    # lexeme but don't start the entry. amol words[5] is not in the lexeme at
    # all, want to not grab the entry in goodmatches so we go to the else
    # statement
    goodmatches = [gm for gm in soup.find('ul').find_all('span', 'goodmatch')
                   if stem.text in gm.parent.text]
    goodmatches = [gm for gm in goodmatches if 'class' in gm.parent.attrs and
                   'lexeme' in gm.parent.attrs['class']]
    if len(goodmatches) == 0:
        entries = [gm.parent for gm in
                   soup.find('ul').find_all('span', 'goodmatch')]
    else:
        entries = [gm.parent.parent for gm in goodmatches]
        lexs = [entr.find('span', 'lexeme').text.replace('(', '').strip()
                for entr in entries]
        entries = [entr for entr, lex in zip(entries, lexs) if stem.text in lex]
    lexemes = []
    parts_of_speech = []
    plurals = []
    participles = []
    genders = []
    for entr in entries:
        lex = entr.find('span', 'lexeme').text.replace('(', '').strip()
        lexemes.append(lex)
        try:
            pos = entr.find('span', 'grammar').text.split(',')[0]
            if not pos.startswith('plural') and not pos.startswith('gender'):
                parts_of_speech.append(pos.strip())
            else:
                parts_of_speech.append(None)
        except AttributeError:
            parts_of_speech.append(None)
        try:
            plural = entr.find('span', 'grammar')
            if not plural.text.startswith('plural'):
                plural.text.split(',')[1]
            plural_text = plural.next_sibling.split(',')[0].replace('(','').strip()
            if plural.next_sibling.next_sibling.attrs['class'] == ['hebrew']:
                plural_text += f' ({plural.next_sibling.next_sibling.text})'
            plurals.append(plural_text)
        except (IndexError, AttributeError):
            plurals.append(None)
        part = entr.find('span', string='participle')
        if part is not None:
            participles.append(part.next_sibling.text.replace(',', '').strip())
        else:
            participles.append(None)
        gdr = entr.find('span', 'grammar', string=re.compile(r'gender.*'))
        if gdr is not None:
            genders.append(gdr.text.replace(',', '').replace('gender', '').strip())
        else:
            genders.append(None)
    definitions = [entr.find('span', 'definition').text for entr in entries]
    # we sometimes get duplicates for some reason, so we do this to make sure
    # each entry is unique
    definitions = set([(pos, defi, gdr, part, pl, lex) for pos, defi, gdr, part, pl, lex
                       in zip(parts_of_speech, definitions, genders,
                              participles, plurals, lexemes)])
    ky['definitions'] = [dict(zip(['partOfSpeech', 'text', 'gender', 'participle',
                                   'plural', 'lexeme'], word)) for word in definitions]
    return ky


def kentucky_definition(wordlist):
    """Get definition for wordlist from Kentucky Yiddish dictionary.

    Kentucky Yiddish Dictionary is at
    https://www.cs.uky.edu/~raphael/yiddish/dictionary.cgi. We use selenium to
    get definitions (so chrome / chromium is required and a browser will open
    while grabbing the info).

    Parameters
    ----------
    wordlist : dict
        Dictionary whose keys are words to check from Kentucky dictionary.
        Values are ignored.

    Returns
    -------
    wordlist : dict
        The input dictionary, with a kentucky entry added (entry is a list of
        dictionaries)

    """
    dictionary_url = 'https://www.cs.uky.edu/~raphael/yiddish/dictionary.cgi'
    browser = webdriver.Chrome()
    browser.get(dictionary_url)
    for word in wordlist.keys():
        wordlist[word]['kentucky'] = _get_word_from_kentucky(browser, word)
    return wordlist


def initialize_wordlist(text):
    """Initialize wordlist.

    Convert text of story to the initial wordlist. This returns a dictionary
    whose keys are the words and whose values are dictionaries with a single
    key, "index", whose values are lists containing the indices of that word in
    the story.

    Before extracting the word indices, we strip all newlines, punctuation, and
    digits.

    Parameters
    ----------
    text : str
        Single string containing a complete Yiddish story.

    Returns
    -------
    wordlist : dict
        Initial wordlist, see above for description.

    """
    # remove newlines
    text = text.replace('\n', ' ')
    # remove all punctuation
    punct = string.punctuation + '—“„'
    text = text.translate(str.maketrans(' ', ' ', punct))
    # remove all digits
    text = text.translate(str.maketrans('', '', '0123456789'))
    # split text into words
    text = np.array([t for t in text.split(' ') if t])
    # get the indices for each word
    wordlist = dict([(t, {'index': np.where(text==t)[0].tolist()})
                     for t in set(text)])
    for word in wordlist.values():
        word['count (story)'] = len(word['index'])
        word['frequency (story)'] = word['count (story)'] / len(text)
    return wordlist


def main(text, dictionaries=['wiktionary', 'kentucky']):
    """Convert Yiddish text to vocabulary list.

    Parameters
    ----------
    text : str
        Single string containing a complete Yiddish story.
    dictionaries : list
        Some subset of {'wiktionary', 'kentucky'}. The dictionaries to check.

    Returns
    -------
    wordlist : dict
        Vocabulary list, dictionary with Yiddish words as keys.

    """
    wordlist = initialize_wordlist(text)
    if 'wiktionary' in dictionaries:
        wordlist = wiktionary_definition(wordlist)
    if 'kentucky' in dictionaries:
        wordlist = kentucky_definition(wordlist)
    return wordlist


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Construct vocabulary list based on Yiddish text.")
    parser.add_argument('input_path', help="Path to the story to read in. Should be a .txt or other plaintext file.")
    parser.add_argument('--output_path', '-o', default=None,
                        help=("Path to save the vocabulary list at. Should be a json. If unset, "
                              "we save a json with the same name as the input."))
    parser.add_argument("--dictionaries", '-d', nargs='+', default=['wiktionary', 'kentucky'],
                        choices=['wiktionary', 'kentucky'],
                        help="Which dictionaries to check for definitions.")
    args = vars(parser.parse_args())
    output = args.pop('output_path')
    if output is None:
        output = op.splitext(args['input_path'])[0] + '.json'
    elif not output.endswith('json'):
        raise ValueError("output_path must end in .json!")
    with open(args['input_path']) as f:
        text = f.read()
    wordlist = main(text, args['dictionaries'])
    with open(output, 'w') as f:
        json.dump(wordlist, f)
