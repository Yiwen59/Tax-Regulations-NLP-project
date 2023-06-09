#!/usr/bin/env python3

import requests
#import json
import csv
import sys
import html
import collections
#import dload
import docx # for reading docx
import fitz # for reading PDFs
from pathlib import Path

#api_key = '6ZMV3bxTtoj5jMMSW85N4wwDhkAjtlwonDLmWVVq'
# extra 
api_key = 'EBO9en2lTQicpTfmASGa2p5EvsN10dvSWPDmBnjJ'
regs_api_url = lambda request: ('https://api.regulations.gov/v4/%s&api_key=%s' % (request, api_key))
fedregs_api_url = lambda doc_num: ('https://www.federalregister.gov/api/v1/documents/%s.json?fields%%5B%%5D=regulations_dot_gov_info' % (doc_num))
fedregs_search_api_url = lambda reg_num: ('https://www.federalregister.gov/api/v1/documents.json?fields%%5B%%5D=regulations_dot_gov_info&per_page=20&conditions%%5Bdocket_id%%5D=%s' % reg_num)
filename = sys.argv[2] if (len(sys.argv) > 2) else 'iloveyouuuu.csv'

fieldnames = [
'id',
'self',
'commentOn',
'commentOnDocumentId',
'commentWordCount',
'duplicateComments',
'address1',
'address2',
'agencyId',
'city',
'category',
'comment',
'country',
'displayProperties',
'docAbstract',
'docketId',
'documentNumber',
'documentType',
'email',
'fax',
'field1',
'field2',
'fileFormats',
'firstName',
'govAgency',
'govAgencyType',
'objectId',
'openForComment',
'lastName',
'legacyId',
'modifyDate',
'organization',
'originalDocumentId',
'pageCount',
'phone',
'postedDate',
'postmarkDate',
'reasonWithdrawn',
'receiveDate',
'restrictReason',
'restrictReasonType',
'stateProvinceRegion',
'submitterRep',
'submitterRepAddress',
'submitterRepCityState',
'subtype',
'title',
'trackingNbr',
'withdrawn',
'zip',
'fileName',
'fileLinks',
'numIncluded'
]

def word_count(string):
  counts = collections.Counter()
  words = string.lower().split()
  for word in words:
    counts.update(words)
  return len(counts)

def get_pdf_string(link):
  r = requests.get(link, stream=True)
  pdf_content = r.content
  doc = fitz.open(stream=pdf_content, filetype='pdf')
  words = []
  for page in doc:
    # other types of extractions can be used to get dicts of words etc
    words.extend(page.get_text('words'))
  print(len(words))

def get_docx_string(link):
  r = requests.get(link, stream=True)
  # can't figure out how to get proper file-like object
  #temp_file_path = '/Users/emilyerdman/projects/mandiaccountingstuff/temp_docx.docx'
  temp_file_path = '/Users/chrissymo/Documents/MSIS/research/with Amanda/fetch data codes/temp_docx.docx'
  with open(temp_file_path, 'wb') as f:
    f.write(r.content)
  doc = docx.Document(temp_file_path)
  for paragraph in doc.paragraphs:
    print(paragraph.text)

#get_docx_string('https://downloads.regulations.gov/IRS-2016-0015-0125/attachment_1.docx')

if len(sys.argv) > 3 and sys.argv[3] == 'skip':
  docket_ids = {
'IRS-2019-0023': '2019-09515',
'IRS-2019-0025': '2019-11292'
  }
else:
  # get the fegreg document numbers from the provided file
  fedreg_docnums = []
  fedregs_file = sys.argv[1]
  fedregs_file = '/Users/chrissymo/Documents/MSIS/research/with_Amanda/fetch_data_codes/test_1216.csv'
  with open(fedregs_file, 'r') as fedregs:
    print('Getting docnums from provided csv file...')
    reader = csv.reader(fedregs)
    headers = next(reader)
    docnum_col = 0
    for i, header in enumerate(headers, start=0):
      if header == 'document_number':
        docnum_col = i
        break
    for row in reader:
      print('   %s' % row[docnum_col])
      fedreg_docnums.append(row[docnum_col].strip())
  print('Finished getting fedreg_docnums.')


  # get document id from the RIN
  docket_ids = {}
  print('Getting docket_ids from fedregs.gov...')
  for fedreg_docnum in fedreg_docnums:
    response = requests.get(fedregs_api_url(fedreg_docnum))
    if response.status_code == 404:
      # look for ones using the reg num
      print('   Couldn\'t find document using %s' % fedreg_docnum)
      continue
    rin = response.json()
    if 'regulations_dot_gov_info' in rin and 'docket_id' in rin['regulations_dot_gov_info']:
      docket_id = rin['regulations_dot_gov_info']['docket_id']
      if (docket_id in docket_ids):
        print('   Found a duplicate docket_id for %s - %s' % (fedreg_docnum, docket_id))
      else:
        print('   Fedreg docnum %s -- %s' % (fedreg_docnum, rin['regulations_dot_gov_info']['docket_id']))
        docket_ids[rin['regulations_dot_gov_info']['docket_id']] = fedreg_docnum
    else:
      print('   Skipped fedreg docnum -- couldn\'t find docket_id for %s' % fedreg_docnum)
  print('Finished getting docket_ids.')
  

# open csv writer to write for each docketId
with open(filename, 'w', newline='') as csvfile:
  print('Getting comment data for docket_ids...')
  writer = csv.DictWriter(csvfile, fieldnames = fieldnames, lineterminator='\n')
  writer.writeheader()

  # first need to get all documents for the given docket_id
  for docket_id in docket_ids:
    print('   On docket %s...' % docket_id)
    documents_url = regs_api_url("documents?filter[docketId]=%s" % docket_id)
    documents = requests.get(documents_url).json()
    # go through each and get comments for each object_id
    if 'data' in documents: 
      for response_object in documents['data']:
        all_comments = []
        object_id = response_object['attributes']['objectId']
        comments_url = regs_api_url('comments?filter[commentOnId]=%s&page[size]=250' % object_id)
        comments = requests.get(comments_url).json()
        print('   Looking at comments for document %s...' % object_id)

        # check to see if there is another page of comments
        comment_count = 0
        page = 0
        last_modified_date = '1000-01-01 01:00:00'
        last_seen_modified_date = ''
        total_comments = 0
        comment_pages = 0
        if 'meta' in comments:
          total_comments = comments['meta']['totalElements']
          comment_pages = comments['meta']['totalPages']



        while comment_count < total_comments:
          if (page < 20):
            page += 1
          else:
            # we're at the end of the pages, start looking at the next group
            page = 1
            last_seen = datetime.datetime.strptime(last_seen_modified_date, '%Y-%m-%dT%H:%M:%SZ')
            last_modified_date = (last_seen + datetime.timedelta(hours=-4)).strftime('%Y-%m-%d %H:%M:%S')
            # HORRIBLE function means we need to subtract 4 hours from the last seed modified date


          print('      On page %s of %s' % (page, comment_pages))
          comments_url = regs_api_url('comments?filter[commentOnId]=%s&filter[lastModifiedDate][ge]=%s&page[size]=250&page[number]=%s&sort=lastModifiedDate,documentId' % (object_id, last_modified_date, page))
          comments = requests.get(comments_url).json()
          # go through each of the comments to add the to the total comments
          if 'data' in comments:
            for comment_object in comments['data']:
              comment_id = comment_object['id']
              # get additional info for each comment
              comment_url = regs_api_url('comments/%s?include=attachments' % comment_id)
              comment = requests.get(comment_url).json()
              all_comments.append(comment)
              print ('      Adding comment for document %s' % object_id)
          else:
            print('   No comment data for document %s.' % object_id)
            continue

          if len(all_comments) > 0:
            print('   Formatting comments for writing.')
          else:
            print('   No comments found.')
            continue
          for comment in all_comments:
            # format comment for writing
            if 'data' in comment:
              formatted_comment = comment['data']['attributes']
              # unescape the html text from the comment and title
              comment_unescaped_html = comment['data']['attributes']['comment']
              if comment_unescaped_html is not None:
                formatted_comment['comment'] = html.unescape(comment_unescaped_html)
              formatted_comment['id'] = comment['data']['id']
              formatted_comment['self'] = "%s?api_key=%s" % (comment['data']['links']['self'], api_key)
              comment_word_count = 0
              if comment_unescaped_html is not None:
                comment_word_count = word_count(comment_unescaped_html)
              formatted_comment['commentWordCount'] = comment_word_count
              num_included = 0
              link_list = []
              if 'included' in comment: 
                formatted_comment['fileName'] = comment['included'][0]['attributes']['title']
                for included in comment['included']:
                  num_included += 1
                  if (('attributes' in included) and ('fileFormats' in included['attributes']) and (included['attributes']['fileFormats'] != None)):
                    for files in included['attributes']['fileFormats']:
                      link_list.append(files['fileUrl'])
              formatted_comment['fileLinks'] = ' '.join(link_list)
              formatted_comment['numIncluded'] = num_included
              formatted_comment['documentNumber'] = docket_ids[docket_id]
              writer.writerow(formatted_comment)
              comment_count += 1
              last_seen_modified_date = comment['data']['attributes']['modifyDate']
            else:
              print('      Skipped comment -- No data.')
    else:
      print('Skipped docket -- No data %s' % docket_id)       

print('CSV written at %s/%s' % (Path.cwd(), filename))
'''
COMMENT OBJECT FROM API FOR REFERENCE
[{
'data': 
  {
  'id': 'IRS-2020-0030-0006', 
  'type': 'comments', 
  'links': 
    {
    'self': 'https://api.regulations.gov/v4/comments/IRS-2020-0030-0006'
    }, 
  'attributes': 
    {
    'commentOn': '09000064847ffe3a', 
    'commentOnDocumentId': 'IRS-2020-0030-0001', 
    'duplicateComments': 0, 
    'address1': None, 
    'address2': None, 
    'agencyId': 'IRS', 
    'city': 'Flower Mound', 
    'category': None, 
    'comment': 'Attached is a document addressing issues that appear to be overlooked in evaluating basis sold when selling more than one type of partnership in one sale. Specifically, it is agreed that an equitable apportionment should be determined. However, equitable apportionment should not mean that it is only based on relative fair market values of components sold. Rather, it should also take into account rights, remedies, etc. of each class such that the purchased or sold interest does not put the new incoming partner on a different economic footing from the same class of partners that he joins. See attached file(s)', 
    'country': 'United States', 
    'displayProperties': None, 
    'docAbstract': None, 
    'docketId': 'IRS-2020-0030', 
    'documentType': 'Public Submission', 
    'email': None, 
    'fax': None, 
    'field1': None, 
    'field2': None, 
    'fileFormats': None, 
    'firstName': 'Brad', 
    'govAgency': None, 
    'govAgencyType': None, 
    'objectId': '09000064848aef6e', 
    'lastName': 'Hoskins', 
    'legacyId': None, 
    'modifyDate': '2020-10-01T19:42:26Z', 
    'organization': None, 
    'originalDocumentId': None, 
    'pageCount': 0, 
    'phone': None, 
    'postedDate': '2020-10-01T04:00:00Z', 
    'postmarkDate': None, 
    'reasonWithdrawn': None, 
    'receiveDate': '2020-10-01T04:00:00Z', 
    'restrictReason': None, 
    'restrictReasonType': None, 
    'stateProvinceRegion': 'TX', 
    'submitterRep': None, 
    'submitterRepAddress': None, 
    'submitterRepCityState': None, 
    'subtype': 'Public Comment', 
    'title': 'Comment from Brad Hoskins, ', 
    'trackingNbr': '1k4-9j9u-hwir', 
    'withdrawn': False, 
    'zip': None, 
    'openForComment': False
    }, 
  'relationships': 
    {
    'attachments': 
      {
      'data': 
        [{
        'id': '09000064848aef8d', 
        'type': 'attachments'
        }], 
      'links': 
        {
        'self': 'https://api.regulations.gov/v4/comments/IRS-2020-0030-0006/relationships/attachments', 
        'related': 'https://api.regulations.gov/v4/comments/IRS-2020-0030-0006/attachments'
        }
      }
    }
  }, 
'included': 
  [{
  'id': '09000064848aef8d', 
  'type': 'attachments', 
  'links': 
    {
    'self': 'https://api.regulations.gov/v4/attachments/09000064848aef8d'
    }, 
  'attributes': 
    {
    'agencyNote': None, 
    'authors': None, 
    'docAbstract': None, 
    'docOrder': 1, 
    'fileFormats': 
      [{
      'fileUrl': 'https://downloads.regulations.gov/IRS-2020-0030-0006/attachment_1.docx', 
      'format': 'docx', 
      'size': 26661
      }, 
      {'
      fileUrl': 'https://downloads.regulations.gov/IRS-2020-0030-0006/attachment_1.pdf', 
      'format': 'pdf', 
      'size': 88242
      }], 
    'modifyDate': '2020-10-01T16:08:37Z', 
    'publication': None, 
    'restrictReason': None, 
    'restrictReasonType': None, 
    'title': 'Carried Interest Regs - Analysis of Example 5 08032020'
    }
  }]
}]
'''