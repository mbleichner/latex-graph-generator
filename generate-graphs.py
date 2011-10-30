#!/usr/bin/python
# -*- coding: iso-8859-1 -*-

import re,sys,os,codecs

translations = {
  'lemma':       'Lemma',
  'theorem':     'Satz',
  'corollary':   'Korollar',
  'mainlemma':   'Hauptlemma',
  'result':      'Ergebnis',
  'proposition': 'Proposition',
  'fact':        'Fakt',
  'remark':      'Bemerkung',
  'observation': 'Beobachtung',
}

colors = {
  'chapter-1':   '#FFFD79',
  'chapter-2':   '#A3FC82',
  'chapter-3':   '#CCCBFF',
  'chapter-4':   '#EEB7EC',
  'chapter-5':   '#C4F9FF',
}

# environments that get a number
numbered  = ['lemma', 'mainlemma', 'corollary', 'theorem', 'proposition', 'fact', 'result', 'remark', 'observation']

# environments that should be included in the graph
graphable = ['lemma', 'mainlemma', 'corollary', 'theorem', 'proposition', 'fact', 'result', 'remark', 'observation']

# environments that require no proof
proofless = ['fact']

# ref commands that produce edges in the graph
refs      = ['ref', 'graphref', 'prettyref', 'vref']

# open and read input file
infilename = sys.argv[1]
assert infilename.endswith('.tex')
infile = codecs.open(infilename, 'r', encoding='latin-1')

content = ''.join([line for line in infile.readlines() if not line.startswith('#')])
infile.close()

# resolve includes
for match in re.finditer(r'\\include\{(.+?)\}', content):
  fn = match.group(1)
  content = content.replace(match.group(0), ''.join(codecs.open(fn+".tex", 'r', encoding='latin-1').readlines()))

# parse tokens
tokens = []
for line in content.split('\n'):
  line = line.strip()
  if not line or line[0] == '%': continue
  for match in re.finditer(r'\\([a-z]+)\{(.+?)\}', line):
    token = (match.group(1), match.group(2))
    tokens.append(token)

# initialize counters and variables
chapter = -1
number  = 0
nodes   = []
active  = []

# iterate over tokens and collect information
for i, (command, argument) in enumerate(tokens):

  if command == 'chapter':
    chapter += 1
    number = 0

  if command == 'begin':
    active.append(argument)

  if command == 'begin' and argument in numbered:
    number += 1

  if command == 'begin' and argument in graphable:
    node = {}
    node['id']        = 'theorem.%i.%i' % (chapter, number) # ID used in LaTeX .thm files
    node['label']     = 'autolabel:%i' % i                  # label defined by \label{}
    node['type']      = argument
    node['chapter']   = chapter
    node['number']    = '%i.%i' % (chapter, number)
    node['parents']   = set([])
    node['invisible'] = set([])
    node['page']      = '??'
    node['proven']    = argument in proofless
    nodes.append(node)

  if command == 'begin' and argument == 'corollary' and len(nodes) > 1:
    nodes[-1]['parents'].add(nodes[-2]['label'])

  if command == 'end':
    assert active.pop() == argument, "expected: %s" % argument

  if command == 'end' and argument == 'proof':
    nodes[-1]['proven'] = True

  if command == 'label' and set(active).intersection(graphable):
    nodes[-1]['label'] = argument

  if command == 'graphcaption' and set(active).intersection(graphable):
    nodes[-1]['caption'] = unicode(argument).replace('>', '&gt;').replace('<', '&lt;').replace('\\n', '<BR/>')

  if command == 'graphattr' and set(active).intersection(graphable):
    nodes[-1]['attr'] = unicode(argument)

  if command in refs and nodes and not nodes[-1]['proven'] and not argument == nodes[-1]['label']:
    nodes[-1]['parents'].add(argument)
    print "ref in chapter", chapter, ':', argument, '->', nodes[-1]['label']

  if command == 'invref' and nodes and not nodes[-1]['proven'] and not argument == nodes[-1]['label']:
    nodes[-1]['invisible'].add(argument)
    print 'invref in chapter', chapter, ':', argument, '->', nodes[-1]['label']

# create indexes for faster access
nodesByLabel = {}
nodesByChapter = {}
nodesById = {}
for node in nodes:
  nodesByLabel[node['label']]     = node
  nodesById[node['id']]           = node
  nodesByChapter[node['chapter']] = nodesByChapter[node['chapter']]+[node] if nodesByChapter.has_key(node['chapter']) else [node]

# extract page numbers from .thm file
if os.path.isfile(infilename[:-4]+'.thm'):
  thmfile = codecs.open(infilename[:-4]+'.thm', 'r', encoding='latin-1')
  lines = [line.strip() for line in thmfile.readlines()]
  for line in lines:
    match = re.search(r'.+\{([0-9]+)\}\{([a-z0-9\.]+)\}', line)
    if match and nodesById.get(match.group(2)):
      nodesById[match.group(2)]['page'] = match.group(1)
  thmfile.close()

# remove dead references
for node in nodes:
  for parentlabel in list(node['parents']):
    parentnode = nodesByLabel.get(parentlabel)
    if not parentnode:
      node['parents'].remove(parentlabel)

# calculate the set of all (direct) children for every node
for node in nodes:
  if not node.has_key('children'):
    node['children'] = set()
for node in nodes:
  for parentlabel in list(node['parents']):
    parent = nodesByLabel[parentlabel]
    parent['children'].add(node['label'])

# calculate the set of all ancestors of every node
def get_ancestors(node):
  ancestors = set(node['parents'])
  for parentnode in [nodesByLabel[label] for label in node['parents']]:
    ancestors = ancestors.union(get_ancestors(parentnode))
  return ancestors
for node in nodes:
  try: node['ancestors'] = get_ancestors(node)
  except: print "recursion in ancestors of node", node['label']

# remove transitively implied edges
for node in nodes:
  for parentnode in [nodesByLabel[label] for label in node['parents']]:
    if [label for label in parentnode['children'] if label in node['ancestors']]:
      print 'redundant edge:', parentnode['number'], '->', node['number']
      node['parents'].remove(parentnode['label'])
      parentnode['children'].remove(node['label'])

# outputs given nodes and all direct parents/children as dot-file.
def draw_graph(nodes, outfilename):
  outfile = codecs.open(outfilename, 'w', encoding='utf-8')
  outfile.write("digraph Relations {\n")
  outfile.write('mclimit=10;\n')
  outfile.write('nodesep=0.2;\n')
  outfile.write('ranksep=0.3;\n')
  outfile.write('node [fontname="Arial" margin=0.02 shape="ellipse" style="filled" fontsize="9"];\n');
  for n in [n for n in nodes if n['type'] in graphable]:
    caption = '<FONT FACE="Arial Bold">%s %s</FONT><BR/>%s<BR/><FONT FACE="Arial Italic">- Seite %s -</FONT>' % (translations.get(n['type']), n['number'], n.get('caption') or n['label'], n['page'])
    color = colors.get('chapter-%i' % n['chapter'])
    attr = node['attr'] if node.has_key('attr') else ''
    outfile.write('"%s" [label=<%s> fillcolor="%s" URL="%s-chap%i.svgz" %s];\n' % (n['id'], caption, color, infilename[:-4], n['chapter'], attr))
  for sourcenode in [n for n in nodes if n['type'] in graphable]:
    parentnodes = [nodesByLabel[label] for label in sourcenode['parents']]
    for parentnode in [n for n in parentnodes if n['type'] in graphable and n in nodes]:
      outfile.write('"%s" -> "%s";\n' % (parentnode['id'], sourcenode['id']))
    parentnodes = [nodesByLabel[label] for label in sourcenode['invisible']]
    for parentnode in [n for n in parentnodes if n['type'] in graphable and n in nodes]:
      outfile.write('"%s" -> "%s" [color="invis"];\n' % (parentnode['id'], sourcenode['id']))
  outfile.write("}")
  outfile.close()

generated_dot_files = []

# draw a complete graph
outfilename = "%s-complete.dot" % infilename[:-4]
draw_graph(nodes, outfilename)
generated_dot_files.append(outfilename)

# draw graphs for every chapter
for chapter, chapternodes in nodesByChapter.items():
  outfilename = "%s-chap%i.dot" % (infilename[:-4], chapter)
  labels_to_draw = set()
  for node in chapternodes:
    labels_to_draw.add(node['label'])
    labels_to_draw = labels_to_draw.union(node['parents'])
    labels_to_draw = labels_to_draw.union(node['children'])
  nodes_to_draw = [nodesByLabel[label] for label in labels_to_draw]
  draw_graph(nodes_to_draw, outfilename)
  generated_dot_files.append(outfilename)

# run GraphViz to generate graphics
for filename in generated_dot_files:
  os.system('dot -Tpdf "%s" -o "%s.pdf"' % (filename, filename[:-4]))
  os.system('dot -Tpng "%s" -o "%s.png"' % (filename, filename[:-4]))
  os.system('perl -e "s/%%PDF-1.5/%%PDF-1.4/" -p -i "%s.pdf"' % filename[:-4]) # to avoid warnings in PDFtex