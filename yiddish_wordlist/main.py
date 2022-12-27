#!/usr/bin/env python3

import string
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
    - can't assume it will be on the outside list (`text[1]`)
    - can't assume it will be the only word in the span (`text[1]`)
    - entry will be the outermost one where stem is the first word in the lexeme? if there are multiple, take all?
    - if there isn't an entry where the stem is the first word in the lexeme (`text[11]`):
      - take matches where it's in the lexeme
      - take all goodmatches

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
