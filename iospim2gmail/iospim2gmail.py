'''

从iTunes备份中找到ios的短讯，通话记录，然后备份到gmail上去。
支持会话

Created on 2012-02-06

@author: zhangyong


'''
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import imaplib, email.utils
import os, datetime, re, csv, hashlib, sqlite3, struct


'''
联系人文件。直接从Google contacts中导出的“Google CSV”格式文件。
'''
contacts_csv_file = 'google_contacts.csv'

'''
您的Gmail账户，注意必须要打开imap才行
'''
username = 'test@gmail.com'
'''
您的Gmail账户密码
'''
password = 'pwd' 

'''Gmail的短讯备份标签，不能用空格，不能用中文。最好别改'''
gmail_sms_label = 'SMS'
'''Gmail的通话记录备份标签，不能用空格，不能用中文。最好别改'''
gmail_call_label = 'CallLog'

myemail = username

'''
备份的路径，一般不需要修改
'''
backup_path = '%APPDATA%\\Apple Computer\\MobileSync\\Backup\\'
'''
gmail imap服务器地址，一般不需要修改
'''
host = 'imap.gmail.com'


#CVS联系人文件中电话号码的列名
phone_keys = ('Phone 1 - Value', 'Phone 2 - Value', 'Phone 3 - Value', 'Phone 4 - Value')
#CVS联系人文件中EMAIL的列名
email_keys = ('E-mail 1 - Value', 'E-mail 2 - Value', 'E-mail 3 - Value')
#这是默认的域
default_domain = 'my_python_sms_backup.com'

#默认编码
charset = 'utf-8'

def formatNumber(number):
    #格式化电话号码
    number = re.sub(r'\D+', '', number)
    if number.startswith('86'):
        number = number[2:]
    return number
 
 
def queryEmailAddrAndNameFromContacts(number, caches):
    #从CSV联系人文件中查找某个联系人对应的email地址
    number = formatNumber(number)     
    if number in caches:
        return caches[number]
  
    with open(contacts_csv_file, 'r', encoding=charset) as csvfile:
        csvreader = csv.DictReader(csvfile)
        for row in csvreader:
            if number in [formatNumber(row[key]) for key in phone_keys if row[key]]:
                emails = [row[key] for key in email_keys if row[key]]
                if emails:
                    email = [tmp for tmp in emails[0].split(':') if tmp][0]
                    caches[number] = email, row['Name']
                else:
                    caches[number] = '', row['Name']
                return caches[number]
        return '', ''

def getEmailAddrAndNameByNumber(number, contactsCaches):
    #通过给定的电话号码，联系人姓名生成发送人的email地址
    addr = None
    name = None
    if os.path.exists(contacts_csv_file):
        addr, name = queryEmailAddrAndNameFromContacts(number, contactsCaches)
        
    if not addr:
        addr = '%s@%s' % (number, default_domain)
    if name:
        addrHdr = Header(name, charset)
        addrHdr.append('<' + addr + '>', 'ascii')
        return  addrHdr, name 
    else:
        addrHdr = Header('<' + addr + '>', 'ascii')
        return  addrHdr, name     
        
def createEmail(number, body, sms_recved, subject_pre, emailIdCaches, contactsCaches):
    #生成email
    if sms_recved:
        fromAddr, name = getEmailAddrAndNameByNumber(number, contactsCaches)
        toAddr = myemail
        senderAddr = Header('<' + '%s@%s' % (number, default_domain) + '>', 'ascii')
    else:
        toAddr, name = getEmailAddrAndNameByNumber(number, contactsCaches)
        fromAddr = myemail
        senderAddr = myemail
    if name:
        subject = '%s with %s(%s) ' % (subject_pre, name, number)
    else:
        subject = '%s with %s ' % (subject_pre, number)
        
    message = MIMEMultipart() 
    message['Subject'] = Header(subject, charset)
    message['From'] = fromAddr
    message['To'] = toAddr
    message['Sender'] = senderAddr 
    message['Reply-To'] = fromAddr
    message['X-Mailer'] = 'Python Sms Backup for IOS,By zhangyong'
        
    if number in emailIdCaches :
        msgId = emailIdCaches[number]
    else:
        msgId = email.utils.make_msgid(domain=default_domain)
        emailIdCaches[number] = msgId
  
    message['Message-Id'] = email.utils.make_msgid(domain=default_domain)
    message['References'] = msgId
    message['In-Reply-To'] = msgId
    message.attach(MIMEText(body, _charset=charset)) 
    return bytes(str(message), charset)


def find_sms_calllog_file_from_mbdb(phone_backp_dir):
    #从mbdb文件中找到短信，通话记录的数据文件名称
    def readStr(file, encoding=charset):
        strLen = struct.unpack('!h', file.read(2))[0] 
        if strLen == -1:
            return ''
        return str(struct.unpack('!%ss' % strLen, file.read(strLen))[0], encoding)
    
    def readStrD(file, encoding=charset):
        strLen = struct.unpack('!h', file.read(2))[0] 
        if strLen == -1:
            return ''
        data = struct.unpack('!%ss' % strLen, file.read(strLen))[0]
        try: 
            return str(data, 'ASCII')
        except:
            return str(data)
    
    manifestmbdb_path = os.path.join(phone_backp_dir, 'Manifest.mbdb')
    manifestmbdb = open(manifestmbdb_path, mode='rb')
    if manifestmbdb.read(6) != b'mbdb\x05\x00' : raise Exception("This does not look like an MBDB file")
    found_file_names = {}
    while (manifestmbdb.tell() + 20) < os.path.getsize(manifestmbdb_path):
        fileinfo = {}
        fileinfo['start_offset'] = manifestmbdb.tell()
        fileinfo['domain'] = readStr(manifestmbdb)
        fileinfo['path'] = readStr(manifestmbdb)
        fileinfo['linkTarget'] = readStr(manifestmbdb)
        fileinfo['DataHash'] = readStrD(manifestmbdb)
        fileinfo['unknown1'] = readStrD(manifestmbdb)
        fileinfo['mode'] = struct.unpack('!h', manifestmbdb.read(2))[0] 
        fileinfo['unknown2'], fileinfo['unknown3'] = struct.unpack('!ii', manifestmbdb.read(8))
        fileinfo['UserId'], fileinfo['GroupId'] = struct.unpack('!ii', manifestmbdb.read(8))
        fileinfo['aTime'], fileinfo['bTime'], fileinfo['cTime'] = struct.unpack('!iii', manifestmbdb.read(12))
        fileinfo['FileLength'], fileinfo['flag'] = struct.unpack('!qb', manifestmbdb.read(9))
        fileinfo['numprops'] = struct.unpack('!b', manifestmbdb.read(1))[0]
        fileinfo['properties'] = {}
        for ii in range(fileinfo['numprops']):
            propname = readStr(manifestmbdb)
            propval = readStrD(manifestmbdb)
            fileinfo['properties'][propname] = propval
            
        if fileinfo['path'] == 'Library/SMS/sms.db':
            data = fileinfo['domain'] + '-' + fileinfo['path']
            found_file_names['sms'] = hashlib.sha1(data.encode(charset)).hexdigest()
        if fileinfo['path'] == 'Library/CallHistory/call_history.db':
            data = fileinfo['domain'] + '-' + fileinfo['path']
            found_file_names['call'] = hashlib.sha1(data.encode(charset)).hexdigest()
        if len(found_file_names) == 2:
            break
    manifestmbdb.close()
    return found_file_names

def doBackupSmsToGmailFromSQLite(imap, file_path, log=True):
    db = sqlite3.connect(file_path)
    emailIdCaches = {}
    contactsCaches = {}
    
    stat, data = imap.select(gmail_sms_label)
    if stat != 'OK':
        imap.create(gmail_sms_label)

    #备份普通消息
    sms_data = db.execute('SELECT address,date,text,flags FROM message where is_madrid==0').fetchall()
    print('正在备份短讯(共%s条)...' % len(sms_data))
    index = 0
    for  address, date, text, flags in sms_data:
        index += 1
        msg = createEmail(address, text, flags == 2, 'SMS', emailIdCaches, contactsCaches)
        stat, data = imap.append(gmail_sms_label, '\SEEN', imaplib.Time2Internaldate(date), msg)
        if stat == 'OK':
            print('\t备份[addr:%s,body:%s],成功!   %s/%s' % (address, text, index, len(sms_data)))
        else:
            print('\t备份[addr:%s,body:%s],失败!   %s/%s' % (address, text, index, len(sms_data)))
    
    #备份iMessage消息
    sms_data = db.execute('SELECT madrid_handle as ADDRESS,(date + 978307200) as DATE,text,madrid_date_read as FLAGS FROM message where is_madrid==1').fetchall()
    print('正在备份短讯(共%s条)...' % len(sms_data))
    index = 0
    for  address, date, text, flags in sms_data:
        index += 1
        msg = createEmail(address, text, flags > 0, 'SMS', emailIdCaches, contactsCaches)
        stat, data = imap.append(gmail_sms_label, '\SEEN', imaplib.Time2Internaldate(date), msg)
        if stat == 'OK':
            print('\t备份[addr:%s,body:%s],成功!   %s/%s' % (address, text, index, len(sms_data)))
        else:
            print('\t备份[addr:%s,body:%s],失败!   %s/%s' % (address, text, index, len(sms_data)))
    db.close()
        
def doBackupCallToGmailFromSQLite(imap, file_path, log=True):
    emailIdCaches = {}
    contactsCaches = {}
    db = sqlite3.connect(file_path)
    
    stat, data = imap.select(gmail_call_label)
    if stat != 'OK':
        imap.create(gmail_call_label)
    
    call_data = db.execute('SELECT address,date,duration,flags FROM call').fetchall()
    print('正在备份通话记录(共%s条)...' % len(call_data))
    index = 0
    for address, date, duration, flags in call_data:
        index += 1
        
        dur = str(datetime.timedelta(seconds=duration))
        typeText = ''
        if flags == 4:
            typeText = 'Incoming Call'
        elif flags == 5:
            typeText = 'Outgoing Call'
        elif flags == 8:
            typeText = 'Blocked Call'
        elif flags == 16:
            typeText = 'Facetime Call'
        elif flags == 65536:
            typeText = 'No network Call'
        elif flags == 1769476:
            typeText = 'Missed Call'
        elif flags == 1048576:
            typeText = 'Dropped Due to Network Prob lems Call'
        else:
            typeText = 'Unknown flags:%s' % flags
                    
        formatAddr = formatNumber(address)
        if formatAddr in contactsCaches:
            name = contactsCaches[formatAddr][1]
        else:
            name = queryEmailAddrAndNameFromContacts(address, contactsCaches)[1]
        if not name:
            name = 'Unknown'   
             
        text = 'Phone number:%s(%s) \r\n Duration:%s \t\nType:%s' % (name, address, dur, typeText) 
        msg = createEmail(address, text, flags != 5, 'Call', emailIdCaches, contactsCaches)
        stat, data = imap.append(gmail_call_label, '\SEEN', imaplib.Time2Internaldate(date), msg)
        if stat == 'OK':
            print('\t备份[addr:%s,body:%s],成功!   %s/%s' % (address, text, index, len(call_data)))
        else:
            print('\t备份[addr:%s,body:%s],失败!   %s/%s   %s' % (address, text, index, len(call_data), data))
    db.close()
        
def backup(logd=True):  
    print('查找备份...')
    real_backup_path = os.path.expandvars(backup_path)
    phone_backp_dirs = [os.path.join(real_backup_path, dir_name) for dir_name in os.listdir(real_backup_path)]
    
    if len(phone_backp_dirs) > 0:
        print('找到备份...', phone_backp_dirs)
    else:
        print('没有找到备份!')
        return False
    
    print('连接到GMAIL服务器...')
    imap = imaplib.IMAP4_SSL(host) 
    print('正在登陆...')
    status, data = imap.login(username, password)
    
    if status != 'OK': 
        print('连接失败！%s' % data)  
        return False   
    for phone_backp_dir in phone_backp_dirs:
        print('正在从备份:%s中查找短讯，通讯录数据...' % phone_backp_dir)
        found_file_names = find_sms_calllog_file_from_mbdb(phone_backp_dir)
        found_file_names['sms'] = os.path.join(phone_backp_dir, found_file_names['sms'])
        found_file_names['call'] = os.path.join(phone_backp_dir, found_file_names['call'])
        doBackupSmsToGmailFromSQLite(imap, found_file_names['sms'])
        doBackupCallToGmailFromSQLite(imap, found_file_names['call'])
    imap.logout()
    print('备份完毕！')
    
if __name__ == '__main__':
    backup()