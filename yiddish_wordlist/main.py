#!/usr/bin/env python3

import string
import re
import os.path as op
import numpy as np
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
    for word in wordlist.keys():
        wordlist[word]['wiktionary'] = parser.fetch(word)
    return wordlist


def _get_word_from_kentucky(browser, word):
    """Construct dictionary with definition for a single word.

    when finding a match:
    - it will be a span/goodmatch
    - can't assume it will be the first / last / anything
    - can't assume it will be on the outside list
    - can't assume it will be the only word in the span
    - entry will be have the stem in the lexeme, if there are multiple, take all.
    - if there isn't an entry where the stem is in the lexeme: take all goodmatches

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
    return dict([(t, {'index': np.where(text==t)[0].tolist()})
                 for t in set(text)])


def main(text):
    """
    """
    if op.exists(text):
        with open(text) as f:
            text = f.read()
    text = initialize_wordlist(text)


if __name__ == '__main__':
    main()
    pass
