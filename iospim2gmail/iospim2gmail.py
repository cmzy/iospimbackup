'''

将iTools从iPhone中导出.csv文件中的短信备份到GMAIL中去
支持会话

Created on 2012-02-06

@author: zhangyong


'''
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import imaplib, time, re, csv, os, email.utils

#联系人文件
contacts_csv_file = 'google_contacts.csv'
#短信文件
sms_csv_file = 'sms_data.csv'

myemail = 'test@gmail.com'
username = myemail  
password = 'pwd'  

host = 'imap.gmail.com'

#Gmail的备份标签
gmail_label = 'SMS'

#CVS联系人文件中电话号码的列名
phone_keys = ('Phone 1 - Value', 'Phone 2 - Value', 'Phone 3 - Value', 'Phone 4 - Value')
#CVS联系人文件中EMAIL的列名
email_keys = ('E-mail 1 - Value', 'E-mail 2 - Value', 'E-mail 3 - Value')

#这是默认的域
default_domain = 'my_python_sms_backup.com'
X_Mailer = 'Python Sms Backup for IOS,By zhangyong'

#默认编码
charset = 'utf-8'


def formatNumber(number):
    number = re.sub(r'\D+', '', number)
    if number.startswith('86'):
        number = number[2:]
    return number
 
 
def getEmailAddrFromContacts(number, name, caches):
    #从CSV联系人文件中查找某个联系人对应的email地址
    if not caches :
        caches = {}
    number = formatNumber(number)     
    if(number in caches):
        return caches[number]
    with open(contacts_csv_file, 'r', encoding=charset) as csvfile:
        csvreader = csv.DictReader(csvfile)
        for row in csvreader:
            if number in [formatNumber(row[key]) for key in phone_keys if row[key]] or name == row['Name']:
                emails = [row[key] for key in email_keys if row[key]]
                if emails:
                    caches[number] = emails[0]
                    return emails[0];
        return None  


def createImapConnect(log=False):
    imap = imaplib.IMAP4_SSL(host) 
    if log:
        print('Connecting to %s...' % host) 
    status, data = imap.login(username, password)
    if log:
        print('Login:%s' % status) 
    return  imap;

def closeImapConnect(imap, log=False):
    imap.logout()
    if log:
        print('Closed') 

def createAddrByNumber(number, name=None, contactEmailCaches=None, queryContacts=True):
    addr = None;
    if queryContacts and os.path.exists(contacts_csv_file):
        addr = getEmailAddrFromContacts(number, name, contactEmailCaches)
    if not addr:
        addr = '%s@%s' % (number, default_domain)
    if name:
        addrHdr = Header(name, charset)
        addrHdr.append('<' + addr + '>', 'ascii')
        return  addrHdr 
    else:
        addrHdr = Header('<' + addr + '>', 'ascii')
        return  addrHdr     
        
def createSmsMsg(number, name, body, sms_type, emailIdCaches, contactEmailCaches):
    if name:
        subject = 'SMS with %s(%s) ' % (name, number)
    else:
        subject = 'SMS with %s ' % number
        
    if sms_type == '接收':
        fromAddr = createAddrByNumber(number, name, contactEmailCaches)
        toAddr = myemail
        senderAddr = createAddrByNumber(number, name, contactEmailCaches, queryContacts=False)
    else:
        toAddr = createAddrByNumber(number, name, contactEmailCaches)
        fromAddr = myemail
        senderAddr = myemail
        
    message = MIMEMultipart() 
    message['Subject'] = Header(subject, charset)
    message['From'] = fromAddr
    message['To'] = toAddr
    message['Sender'] = senderAddr 
    message['Reply-To'] = fromAddr
    message['X-Mailer'] = X_Mailer
    
    if name:
        emailIdKey = name
    else:
        emailIdKey = number
        
    if emailIdKey in emailIdCaches :
        msgId = emailIdCaches[emailIdKey]
    else:
        msgId = email.utils.make_msgid(domain=default_domain);
        emailIdCaches[emailIdKey] = msgId
  
    message['Message-Id'] = email.utils.make_msgid(domain=default_domain);
    message['References'] = msgId
    message['In-Reply-To'] = msgId
    message.attach(MIMEText(body, _charset=charset)) 
    return bytes(str(message), charset)

def appendSmsToGmail(imap, sms_phone, sms_time, sms_body, sms_type, sms_status, emailIdCaches, contactEmailCaches):
    phone_data = sms_phone.split(' ')
    if len(phone_data) == 2:
        number = phone_data[0]
        name = phone_data[1]
        name = name[1:-1]
    else:
        number = phone_data[0] 
        name = None
    datetime = time.strptime(sms_time, '%Y-%m-%d %H:%M:%S')    
    msg = createSmsMsg(number, name, sms_body, sms_type, emailIdCaches, contactEmailCaches)
    status, data = imap.append(gmail_label, '\SEEN', imaplib.Time2Internaldate(datetime), msg)
    return  status, data 

def doBackupToGmail(log=True):
    # Open file
    csvfile = open(sms_csv_file, 'r')
    csvreader = csv.reader(csvfile)
    
    #Open connect and login
    imap = createImapConnect(log) 
    status, data = imap.select(gmail_label)
    if 'OK' != status:
        imap.create(gmail_label)
    imap.select(gmail_label)
    
    emailIdCaches = {}
    contactEmailCaches = {}
    for sms_phone, sms_time, sms_body, sms_type, sms_status in csvreader:
        if sms_phone == '电话号码':
            continue;
        status, data = appendSmsToGmail(imap, sms_phone, sms_time, sms_body, sms_type, sms_status, emailIdCaches, contactEmailCaches)
        if log:
            print('\tAppend msg[%s,%s,%s]:%s' % (sms_phone, sms_type, sms_time, status))
    csvfile.close()
    closeImapConnect(imap, log)
    print('Backup success')
    
if __name__ == '__main__':
    doBackupToGmail()
