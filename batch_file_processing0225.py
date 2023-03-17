# coding: utf-8
import configparser, re
import os, pymssql, socket
import struct
import datetime, time
import csv
import py7zr
# import zipfile
# import shutil


import django

from simple_logger import make_logger


# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'syncTasker.settings')
# django.setup()

logger = make_logger('file-process', log_file='logs/file_process.log')

"""
批量处理文件
"""

# start = datetime.now()
config = configparser.ConfigParser()
config.read("file_processing.config", encoding="utf-8-sig")
score_host = config.get("Socket", "host")
score_port = int(config.get("Socket", "port"))
source_dir = config.get("Address", "source_dir")
target_dir = config.get("Address", "target_dir")
sql_host = config.get("DB", "host")
sql_user = config.get("DB", "user")
sql_pwd = config.get("DB", "pwd")
sql_db = config.get("DB", "db")
score_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
score_socket.connect((score_host, score_port))

flag = True


def link_sqlserver(ip):
    connsql = pymssql.connect(
        host=sql_host,
        user=sql_user,
        password=sql_pwd,
        database=sql_db,
        charset="utf8")
    print("%s已连接AR_Coating数据库" % ip)
    cur = connsql.cursor()
    return connsql, cur


def processing_task(ip):
    dir = os.path.join(source_dir, ip+"_report")
    files_list = os.listdir(dir)
    conn_sql, cur = link_sqlserver(ip)
    cur.execute(
        "select [Country], [Factory], [Machine], [NewestFileID] FROM [ARCoating].[dbo].[ARbigdataMachineRegist] WITH(NOLOCK) where IP='%s'" % (
            ip))
    results = cur.fetchall()
    if len(results) != 0:
        for row in results:
            country = row[0]
            factory = row[1]
            machine = row[2]
            newest_file_id = row[3]
            pre_list = (country, factory, machine, newest_file_id)
            
            num_list = []
            for i in files_list:  # 遍历当前路径下所有非目录子文件
                if i.startswith("EVT"):
                    i = i[3:]
                    i = i.strip(".CSV")
                    i = i.strip(".csv")
                    if i.isdigit():    
                        num_list.append(i)
            
            for i in num_list:
                try:
                    if  int(i) > int(pre_list[3]) and int(i) != int(max(num_list)):
                        send_to_score(conn_sql, cur, pre_list, dir, i, ip, logger, score_socket)
                except IndexError as e:
                    logger.warning(f"【警告】{i}号源文件完整性出现异常，请检查源文件,报错细节：{str(e)}")
                    pass
                except ValueError as e:
                    logger.warning(f"【警告】{i}号源文件数据格式出现异常，请检查源文件,报错细节：{str(e)}")
                    pass
                except Exception as e:
                    logger.warning(f"【警告】{i}号源文件出现异常，请检查源文件,报错细节：{str(e)}")
                    pass
    else:
        logger.warning(f"【提醒】{ip}未注册，请前往服务器注册")


def send_to_score(conn_sql, cur, pre_list, dir, num, ip, logger, score_socket):
    """
    正常生产	（8byte文件长度+128 byte工艺信息及文件名+n byte文件内容）
                4byte+4byte	文件大小（可能先数据后EVT文件大小，也可能反过来）
                128 byte	‘国家名称’|‘工厂名称’|‘机器名称’|‘工艺名称’|‘文件名’|‘文件名’
                n byte	两个文件内容
        示例： 16626740+7915+China|CNMA|19#|BV66Z|17032925.CSV|EVT17032925.CSV+文件字节流
    """
    num_filepath = os.path.join(dir, num + ".csv")
    evt_filepath = os.path.join(dir, "evt" + num + ".csv")
    # score_socket = socket.socket()
    # score_socket.connect((score_host, score_port))
    logger.info(f"{ip}已与评分系统建立连接")
    data_list = get_file_info(cur, pre_list, dir, num, logger)
    logger.info(f'主要数据有:{data_list[2]},{data_list[3]},{data_list[4]},{data_list[5]},{data_list[6]}')
    zip_name = str(num)+".7z"
    # file_folder_name = str(num)
    folder_path = os.path.join(target_dir, data_list[0], data_list[1], data_list[2], data_list[17])
    dir_file_path = os.path.join(folder_path, zip_name)
    # dir_file_path = os.path.join(folder_path, file_folder_name)
    
    if data_list[13] == 1:
        file_data = readfile(num_filepath) + readfile(evt_filepath)
        str1 = (data_list[0] + '|' + data_list[1] + '|' + data_list[2] + '|' + data_list[4] + '|' + data_list[5] + '|' +
                data_list[6]).encode('utf-8')  # 正常生产的工艺信息
        str2 = (data_list[0] + '|' + data_list[1] + '|' + data_list[2] + '|' + data_list[4]).encode('utf-8')  # 机器清洗时的工艺信息
        head_info1 = struct.pack("ii128s", data_list[7], data_list[8], str1)  # 正常生产的数据包
        head_info2 = struct.pack("ii128s", 0, 0, str2)  # 机器清洗时的数据包
        # machine_num = data_list[2].strip("#")  # 机器编号取出待用
        if data_list[15] == 1:
            score_socket.send(head_info2)
            logger.warning(f"【提醒】此次为机器清洗环节")
            print(head_info2,",此次为机器清洗环节")
        else:
            score_socket.send(head_info1)
            score_socket.send(file_data)
        print("已将数据传给评分系统")
        score_socket_request = score_socket.recv(8).decode()
        if score_socket_request == "success":
            print("评分系统反馈:接收数据成功 ")
            datalist_inser_to_sql(conn_sql, cur, data_list, dir_file_path, ip, num)
            logger.info(f'{data_list[5]} & {data_list[6]}文件已成功传送至评分系统"')
            # score_socket.close()
            #   将所接收的文件压缩处理，并删除源文件
            
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            else:
                pass
            make_7z(num_filepath, evt_filepath, dir_file_path)
            # mkdir(dir_file_path)
            # shutil.move(num_filepath, dir_file_path)
            # shutil.move(evt_filepath, dir_file_path)
            logger.info(f"数据源文件已压缩保存完毕，文件名为{zip_name}")
            # logger.info(f"数据源文件已移动至指定文件夹，文件夹名为{file_folder_name}")
            logger.info(f'*' * 50)
        else:
            logger.warning(f"【提醒】评分系统未接收到文件")         
    else:
        logger.warning(f"【提醒】{num}编号只存在单文件，不发送评分，请检查设备机台")
        #   将所接收的文件压缩处理，并删除源文件        
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        else:
            pass       
            make_7z_single(evt_filepath, dir_file_path)
            logger.info(f"数据源文件已压缩保存完毕，文件名为{zip_name},只有EVT单文件")
            # mkdir(dir_file_path)
            # shutil.move(evt_filepath, dir_file_path)
            # logger.info(f"数据源文件已已移动至指定文件夹，文件夹名为{file_folder_name},只有EVT单文件")
            logger.info(f'*' * 50)
    

def get_file_info(cur, pre_list, dir, num, logger):
    '''

    :param num: 文件名数字
    :return:
    双文件都存在时返回字典 = {文件名1，文件名2，国家，工厂，机器号，工艺名，文件尺寸1，文件尺寸2，
    生产日期，开始时间，结束时间}
    '''
    num_filepath = os.path.join(dir, num + ".csv")
    evt_filepath = os.path.join(dir, "evt" + num + ".csv")

    # 工艺名称
    
    recipe_list = read_data_in_csv(evt_filepath, "Recipe Name :", 0, 1, 1)    #工艺名数据名为"Recipe Name :"，数据名是第0个位置，数据是第1个位置，该行长度大于1
    if len(recipe_list) > 0:
        pass
    else:
        recipe_list = read_data_in_csv(evt_filepath, "Recipe Name:", 0, 1, 1)     #工艺名数据名为"Recipe Name:"，数据名是第0个位置，数据是第1个位置，该行长度大于1
        
    str2 = recipe_list[0].strip()
    recipe_full = str2   
    recipe, clean_status = clean_check(str2)
    
    try:
        cur.execute("SELECT [Product] FROM [ARCoating].[dbo].[Proclist_cnma] WITH(NOLOCK) WHERE [ProcessName]= '%s'" % recipe)
        row = cur.fetchone()
        product = row[0]
        error_recipe = 0
        
    except BaseException:
        product = "RecipeCheck"
        error_recipe = 1

    country = pre_list[0]  # 国家名称
    factory = pre_list[1]  # 工厂名称
    machine = pre_list[2]  # 机台名称

    # 生产日期
    
    pd_list = read_data_in_csv(evt_filepath, "Production Start :", 0, 1, 1)   #生产日期数据名为"Production Start :"，数据名是第0个位置，数据是第1个位置，该行长度大于1
    if len(pd_list) > 0:
        pass
    else:
        pd_list = read_data_in_csv(evt_filepath, "Production Start:", 0, 1, 1)    #生产日期数据名为"Production Start:"，数据名是第0个位置，数据是第1个位置，该行长度大于1

    pd = pd_list[0].strip()
    try:
        year_s, mon_s, day_s = pd.split('/')
    except:
        year_s, mon_s, day_s = pd.split('-')
    if int(year_s) > 31:
        process_date = datetime.date(int(year_s), int(mon_s), int(day_s))
    else:
        process_date = datetime.date(int(day_s), int(year_s), int(mon_s))

    # 开始时间
    
    st_list = read_data_in_csv(evt_filepath, "Production Start :", 0, 2, 2)    #生产日期数据名为"Production Start :"，数据名是第0个位置，数据是第2个位置，该行长度大于2
    if len(st_list) > 0:
        pass
    else:
        st_list = read_data_in_csv(evt_filepath, "Production Start:", 0, 2, 2)    #生产日期数据名为"Production Start:"，数据名是第0个位置，数据是第2个位置，该行长度大于2
    st = st_list[0].strip()  
    if re_time_check(st):
        start_time = st
    else:
        start_time = ''

    # 结束时间
    et = read_data_in_csv(evt_filepath, "REM", 1, 0, 2)[-1].strip()    #结束时间需要统计最后一个时间数据，数据名为"REM"，数据名是第1个位置，数据是第0个位置，该行长度大于2
    if re_time_check(et):
        end_time = et
    else:
        end_time = ''

    #结束日期
    process_date_end = when_upload_end(process_date, start_time, end_time)

    # 运行时间
    rt = calculate_of_run_time(process_date, start_time, process_date_end, end_time)
    if re_time_check(et):
        run_time = rt
    else:
        run_time = ''

    # EVT文件名称
    evt_filename = "EVT" + num + ".CSV"
    # EVT文件尺寸
    evt_filesize = os.path.getsize(evt_filepath)

    if os.path.exists(num_filepath):
        file_integrity = 1  # 双文件都存在
        num_filename = num + ".CSV"  # 数字文件名称
        num_filesize = os.path.getsize(num_filepath)  # 数字文件尺寸
        # logger.info(f'主要数据有:{country},{factory},{machine},{recipe},{product},{num_filename},{evt_filename}')
        data_list = [
            country,
            factory,
            machine,
            recipe,
            product,
            num_filename,
            evt_filename,
            num_filesize,
            evt_filesize,
            process_date,
            start_time,
            end_time,
            error_recipe,
            file_integrity,
            process_date_end,
            clean_status,
            run_time,
            recipe_full]
    else:
        file_integrity = 0  # 只存在单文件
        data_list = [
            country,
            factory,
            machine,
            recipe,
            product,
            0,
            evt_filename,
            0,
            evt_filesize,
            process_date,
            start_time,
            end_time,
            error_recipe,
            file_integrity,
            process_date_end,
            clean_status,
            run_time,
            recipe_full]
    return data_list


def datalist_inser_to_sql(conn_sql, cur, datalist, dir_file_path, ip, num):
    """
    [country, factory, machine, recipe, product, filename1, filename2, filesize1, filesize2,
    process_date, start_time, end_time, error_recipe, file_intergrity, process_date_end]
    """

    country = datalist[0]
    factory = datalist[1]
    machine = datalist[2]
    recipe = datalist[3]
    filename1 = datalist[5]
    filename2 = datalist[6]
    filesize1 = datalist[7]
    filesize2 = datalist[8]
    process_date = datalist[9]
    start_time = datalist[10]
    end_time = datalist[11]
    ErrorRecipe = datalist[12]
    intergrity = datalist[13]
    process_date_end = datalist[14]
    run_time = datalist[16]
    recipe_full = datalist[17]
    ip_addr = ip
    # upload_time = datetime.datetime.strftime(datetime.datetime.now(),'%Y-%m-%d %H:%M:%S')
    upload_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    need_clean = '0'
    filePath = dir_file_path

    cur.execute("INSERT INTO [dbo].[ARdataUploadRecord] ([filesize1],[filesize2],[country]"
                ",[factory],[machine],[recipe],[process_date],[start_time],[end_time]"
                ",[integrity],[need_clean],[IP],[upload_time],[ErrorRecipe],[filename1]"
                ",[filename2],[process_date_end], [run_time], [filePath]) VALUES('%s','%s','%s','%s'"
                ",'%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s','%s', '%s'"
                ", '%s', '%s')"%(filesize1,filesize2, country, factory, machine, recipe_full, process_date, start_time
                                           , end_time,intergrity, need_clean, ip_addr, upload_time,ErrorRecipe
                                           , filename1, filename2, process_date_end, run_time, filePath))
    cur.execute("update [ARCoating].[dbo].[ARbigdataMachineRegist] set [NewestFileID] ='%s' where IP='%s'" % (num, ip))
    conn_sql.commit()

# def read_csvfile_line(filepath, line_num, str_num):
#     '''
#
#     :param filepath: csv文件路径
#     :param line_num: 第几行
#     :param str_num: 该行的第几个元素
#     :return: 读取的数据
#     '''
#     if os.path.exists(filepath):
#         with open(filepath, 'r', encoding="utf-8") as csvfile:
#             mLines = csvfile.readlines()
#             targetLine = mLines[line_num]
#             line_str = targetLine.split(',')[str_num]
#     return line_str


def read_data_in_csv(filepath, data_name, data_name_no, data_no, lens):
    '''

    :param filepath: csv文件路径
    :param data_name: 数据名
    :param data_name_no: 数据名位于该行的第几个元素
    :param data_no: 数据名对应的数据位于该行的第几个元素
    :param lens: 该行元素数量。必须大于等于
    :return: 读取的数据列表
    '''
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        list = []
        for row in reader:
            if len(row) > lens:
                if row[data_name_no] == data_name:
                    list.append(row[data_no])
            else:
                pass
    return list


def seconds_turn_to_time(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    t = "%d:%02d:%02d" % (h, m, s)
    return t


def clean_check(rp):
    s = rp.replace(" ", "").replace("_", "").upper()
    a = 'CLEAN'
    b = 'Clean'
    c = 'clean'
    if a in s or b in s or c in s:
        clean_status = 1
    else:
        clean_status = 0
    recipe = s.upper()
    # if "BlueDVS" not in recipe or "DVBp" not in recipe or "BPCN" not in recipe:
    #     recipe = recipe.rstrip("C").rstrip("CX")
    print('Check it in SQL:', recipe)
    return recipe, clean_status


def when_upload_end(process_date, start_time, end_time):
    '''

    :param process_date: 工艺参数生成日期
    :param start_time: 工艺参数开始生成时间
    :param end_time: 工艺参数生成完成时间
    :return: process_date_end 工艺参数生成完成日期
    #0424加入该函数
    '''

    if start_time < end_time:
        date_end = process_date
    else:
        date_end = timedelta("d", process_date, 1)

    process_date_end = date_end
    return process_date_end


def timedelta(sign, dt, value):
    """
    对指定时间进行加减运算，几秒、几分、几小时、几日、几周、几月、几年
    sign: y = 年, m = 月, w = 周, d = 日, h = 时, n = 分钟, s = 秒
    dt: 日期，只能是datetime或datetime.date类型
    value: 加减的数值
    return: 返回运算后的datetime类型值
    """
    if not isinstance(dt, datetime.datetime) and not isinstance(dt, datetime.date):
        raise Exception("日期类型错误")

    if sign == 'y':
        year = dt.year + value
        if isinstance(dt, datetime.date):
            return datetime.datetime(year, dt.month, dt.day)
        elif isinstance(dt, datetime.datetime):
            return datetime.datetime(year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)
        else:
            return None
    elif sign == 'm':
        year = dt.year
        month = dt.month + value
        ### 如果月份加减后超出范围，则需要计算一下，对年份进行处理 ###
        # 如果月份加减后等于0时，需要特殊处理一下
        if month == 0:
            year = year - 1
            month = 12
        else:
            # 对年月进行处理
            year = year + month // 12
            month = month % 12
        if isinstance(dt, datetime.date):
            return datetime.datetime(year, month, dt.day)
        elif isinstance(dt, datetime.datetime):
            return datetime.datetime(year, month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)
        else:
            return None
    elif sign == 'w':
        delta = datetime.timedelta(weeks=value)
    elif sign == 'd':
        delta = datetime.timedelta(days=value)
    elif sign == 'h':
        delta = datetime.timedelta(hours=value)
    elif sign == 'n':
        delta = datetime.timedelta(minutes=value)
    elif sign == 's':
        delta = datetime.timedelta(seconds=value)
    else:
        return None

    return dt + delta


def calculate_of_run_time(data1, time1, data2, time2):
    year_s1, mon_s1, day_s1 = (datetime.datetime.strftime(data1, "%Y/%m/%d")).split('/')
    hour_s1, min_s1, sec_s1 = time1.split(':')
    year_s2, mon_s2, day_s2 = (datetime.datetime.strftime(data2, "%Y/%m/%d")).split('/')
    hour_s2, min_s2, sec_s2 = time2.split(':')
    datatime1 = datetime.datetime(int(year_s1), int(mon_s1), int(day_s1), int(hour_s1), int(min_s1), int(sec_s1))
    datatime2 = datetime.datetime(int(year_s2), int(mon_s2), int(day_s2), int(hour_s2), int(min_s2), int(sec_s2))
    secondsDiff = datatime2 - datatime1
    return secondsDiff


def re_date_check(type_datatime):
    pattern1 = re.compile(r'\d{1,2}/\d{1,2}/\d{4}')
    pattern2 = re.compile(r'\d{4}/\d{1,2}/\d{1,2}')
    if pattern1.search(type_datatime) and pattern2.search(type_datatime) is None:
        # print("没有")
        return False
    else:
        # print("格式符合")
        return True


def re_time_check(type_time):
    pattern = re.compile(r'\d{1,2}:\d{1,2}:\d{1,2}')
    if pattern.search(type_time) is None:
        # print("没有")
        return False
    else:
        # print("格式符合")
        return True


def mkdir(path):
    # 去除首位空格
    path=path.strip()
    # 去除尾部 \ 符号
    path=path.rstrip("\\")
 
    # 判断路径是否存在
    # 存在     True
    # 不存在   False
    isExists=os.path.exists(path)
 
    # 判断结果
    if not isExists:
        # 如果不存在则创建目录
        # 创建目录操作函数
        os.makedirs(path) 
 
        print(path+' 创建成功')
        return True
    else:
        # 如果目录存在则不创建，并提示目录已存在
        print(path+' 目录已存在')
        return False


def readfile(filepath):
    '''

    :param filepath: 需读取的文件地址
    :return: 文件数据流
    '''
    with open(filepath, 'rb') as f:
        filedata = f.read()
    return filedata


def make_zip(file1, file2, dirfile_path):
    '''

    :param file1: EVT文件
    :param file2: 数字文件
    :param zipfilename: 压缩后文件路径
    :return:
    '''
    zf = zipfile.ZipFile(dirfile_path, "w")
    zf.write(file1, arcname=os.path.basename(file1), compress_type=zipfile.ZIP_DEFLATED)
    zf.write(file2, arcname=os.path.basename(file2), compress_type=zipfile.ZIP_DEFLATED)
    zf.close()
    os.remove(file1)
    os.remove(file2)

def make_7z(file1, file2, dirfile_path):
    '''

    :param file1: EVT文件
    :param file2: 数字文件
    :param dirfile_path: 压缩后文件路径
    :return:
    '''
    with py7zr.SevenZipFile(dirfile_path, "w") as zf:
        zf.writeall(file1, arcname=os.path.basename(file1))
        zf.writeall(file2, arcname=os.path.basename(file2))
        zf.close()
        os.remove(file1)
        os.remove(file2)


def make_zip_single(file1, dirfile_path):
    '''

    :param file1: EVT文件
    :param zipfilename: 压缩后文件路径
    :return:
    '''
    zf = zipfile.ZipFile(dirfile_path, "w")
    zf.write(file1, arcname=os.path.basename(file1), compress_type=zipfile.ZIP_DEFLATED)
    zf.close()
    os.remove(file1)


def make_7z_single(file1, dirfile_path):
    '''

    :param file1: EVT文件
    :param dirfile_path: 压缩后文件路径
    :return:
    '''
    with py7zr.SevenZipFile(dirfile_path, "w") as zf:
        zf.writeall(file1, arcname=os.path.basename(file1))
        zf.close()
        os.remove(file1)

# def conn_socket():
#     score_socket = socket.socket()
#     score_socket.connect((score_host, score_port))
#     return score_socket


# def doconnect():
#     """连接服务端server"""
#     try : 
#         score_socket = conn_socket()
#     except ConnectionResetError:
#         print('[网络中断，正在尝试重新连接]')
#         time.sleep(3)
#         score_socket = conn_socket()
#     except socket.error  :
#         print('[服务器端还未启动或者无网络，正在尝试重新连接]')
#         time.sleep(3)
#         score_socket = conn_socket()           
#     except :
#         print('其他错误') 
#         time.sleep(3)
#     return score_socket
    
def run():   
    while 1:
        files_list = os.listdir(source_dir)
        for i in files_list:
            if i.endswith('report'):
                machine_ip = str(i.strip('_report'))
                processing_task(machine_ip)
            else:
                pass
        time.sleep(15)



def dorun():
    try : 
        run()
    except Exception:
        print('正在重启服务......')
        time.sleep(5)
        run()


if __name__ == '__main__':
    dorun()