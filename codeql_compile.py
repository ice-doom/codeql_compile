# coding=utf-8
import pathlib, zipfile, subprocess
import os, sys, time, re
import argparse
import platform
import shutil

# 指定自定义java-decompiler路径
self_java_decompiler_path = r'/java-decompiler.jar'
# 指定自定义ecj的路径
self_ecj_path = r"/ecj-4.6.1.jar"
# 指定自定义procyon的路径
self_procyon_path = r"/procyon.jar"
# 指定自定义codeql的路径
codeql_path = r"/codeql"


def get_arch():
    return platform.system().lower()


# 用来校验本地的ecj、java_decompiler路径是否正确
def verify(file_jar, my_path):
    if pathlib.Path("./{}".format(file_jar)).is_file():
        return "./{}".format(file_jar)
    elif pathlib.Path(my_path).is_file():
        return my_path
    return False


def java_decompiler_run():
    # 搜索源项目中包含.jar的所有路径
    _sub = subprocess.getstatusoutput(
        'java -cp "{}" org.jetbrains.java.decompiler.main.decompiler.ConsoleDecompiler -dgs=true {} {}'.format(
            java_decompiler_path, app_path, save_path))
    if _sub[0] != 0:
        print(_sub[1])
        sys.exit("java_decompiler 执行失败......")
    app_jars_path = sorted(pathlib.Path(save_path).glob('**/*.jar'))
    # 反编译后会生成jar文件，将文件内容解压出来
    for app_jar_path in app_jars_path:
        with zipfile.ZipFile(pathlib.Path.joinpath(app_jar_path), mode='r') as zfile:
            for file in zfile.namelist():
                zfile.extract(file, pathlib.Path.joinpath(save_path, app_jar_path.name.rstrip('.jar')))

        pathlib.Path.joinpath(app_jar_path).unlink()


# 先尝试编译成class，定位错误文件再使用procyon反编译替换
def check():
    _sub = subprocess.getstatusoutput('{0}/{1}'.format(save_path,run))
    # 正则匹配错误文件路径
    re_matchs = set(re.findall("ERROR in (.*)? \(at line", _sub[1]))

    # 确认是否未编译生成class
    try:
        for re_match in re_matchs.copy():
            is_file = pathlib.Path(re_match.replace(".java", ".class")).is_file()
            if is_file:
                re_matchs.remove(re_match)
    except Exception as e:
        print("waring:" + e)

    app_jars_name = [jar_path.name.rstrip('.jar') for jar_path in pathlib.Path(app_path).glob('**/*.jar')]
    error_jars = [app_jar_name for app_jar_name in app_jars_name for re_match in re_matchs if
                  app_jar_name not in re_match]
    error_classes = re_matchs.difference(set(error_jars))
    # 使用 procyon 反编译jar包
    for app_jar_path in pathlib.Path(app_path).glob('**/*.jar'):
        jar_folder = app_jar_path.name.rstrip('.jar')
        if jar_folder in error_jars:
            _sub = subprocess.getstatusoutput(
                'java -jar "{}" {} -o {}/{}'.format(procyon_path, app_jar_path, save_path, jar_folder))

    # 使用 procyon 反编译class文件
    if not os.path.exists(save_path + "/procyon_class"):
        os.mkdir(save_path + "/procyon_class")
    for class_path in error_classes:
        class_path = str(class_path).replace(save_path, app_path).replace(".java", ".class")
        _sub = subprocess.getstatusoutput(
            'java -jar "{}" {} -o {}/procyon_class'.format(procyon_path, class_path, save_path))
    # 将反编译后的文件替换原先文件
    for class_path in pathlib.Path(save_path + "/procyon_class").glob('**/*.java'):
        to_class_path = [class_path for class_path in pathlib.Path(save_path).glob(
            '**/{}'.format(class_path.relative_to("{}/procyon_class".format(save_path)))) if
                         "procyon_class" not in str(class_path)]
        shutil.move(str(class_path), str(to_class_path[0]))

    shutil.rmtree(save_path + "/procyon_class")


# 创建用来编译的脚本，在codeql创建数据库时使用
def compile_cmd_file_create():
    # 准备待编译的jar包
    with open("{}/file.txt".format(save_path), "w+") as f:
        for java_path in pathlib.Path(save_path).glob('**/*.java'):
            f.write(str(java_path) + "\n")
    ecj_absolute_path = pathlib.Path(ecj_path).resolve()
    compile_cmd = "java -jar {} -encoding UTF-8 -8 -warn:none -noExit @{}/file.txt".format(ecj_absolute_path, save_path)

    if dependencies_path:
        libs = ""
        search_jars_path = pathlib.Path(dependencies_path).glob('**/*.jar')
        for search_jar_path in search_jars_path:
            libs += "{};".format(search_jar_path.name)
        compile_cmd = "cd {} && java -jar {} -encoding UTF-8 -classpath \"{}\" -8 -warn:none -noExit @{}/file.txt".format(
            dependencies_path, ecj_absolute_path, libs, save_path)

    with open("{}/run.cmd".format(save_path), "w+") as f:
        f.write(compile_cmd)

    with open("{}/run.sh".format(save_path), "w+") as f:
        f.write(compile_cmd)
        # 给予权限
        if platform.system().lower() != 'windows':
            os.system('chmod u+x {}/run.sh'.format(save_path))


def create_database(app_path, include=None, source=None):
    if source is None:
        source = app_path
    if include is None:
        os.system(
            '{codeql} database create ../{name} -l \"java\" -s \"{source}\" -c \"{run}\"'.format(
                app_path=app_path, codeql=codeql_path,
                name="{0}_database".format(
                    pathlib.Path(
                        app_path).name),
                source=source,
            run=run))
    else:
        os.system("{codeql} database init -s {source} -l \"java\" {name}".format(app_path=app_path,
                                                                                 codeql=codeql_path,
                                                                                 name="{0}_database".format(
                                                                                     pathlib.Path(
                                                                                         app_path).name),
                                                                                 source=source))
        os.system("{codeql} database trace-command {name} {run}".format(app_path=app_path,
                                                                           codeql=codeql_path,
                                                                           name="{0}_database".format(
                                                                               pathlib.Path(
                                                                                   app_path).name),
                                                                        run=run
                                                                           ))
        extend = None
        if include == "xml":
            extend = "xml"
        os.system(
            "{codeql} database index-files --language {include} --include-extension .{extend} {name}".format(
                app_path=app_path,
                codeql=codeql_path,
                include=include,
                extend=extend,
                name="{0}_database".format(
                    pathlib.Path(
                        app_path).name),
            ))
        os.system(
            "{codeql} database finalize {name}".format(
                app_path=app_path,
                codeql=codeql_path,
                include=include,
                extend=extend,
                name="{0}_database".format(
                    pathlib.Path(
                        app_path).name),
            ))


epilog = r'''Example:
python3 codeql_compile.py -l java -a D:\java\apps\cloud -d "D:\java\apps\cloud\lib"  普通创建
python3 codeql_compile.py -l java -a D:\java\apps\cloud -d "D:\java\apps\cloud\lib -i xml"  包含xml文件
'''
parse = argparse.ArgumentParser(epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
parse.add_argument('-l', '--language', help='指定语言')
parse.add_argument('-i', '--include', help='指定要额外包含的文件类型')
parse.add_argument('-a', '--app', help='输入项目根路径')
parse.add_argument('-d', '--dep', help='输入依赖包路径')
parse.add_argument('-c', '--check', help='对java-decompiler反编译内容进行检测', action="store_true")
parse.add_argument('-o', '--out', help='输入刚刚已经反编译好的存放路径')
args = parse.parse_args()
# 指定语言
language = args.language
# 指定源项目路径，就是要被反编译的项目路径
app_path = args.app
# 指定依赖包路径，在编译代码时需要指定，否则代码中存在相关依赖会导致编译失败
dependencies_path = args.dep
save_path = args.out
# 指定要包含的文件
include = args.include
# 脚本类型
run = None
if "windows" == get_arch():
    run = "./run.sh"
else:
    run = "run.cmd"

if __name__ == '__main__':
    if language == "java":
        if app_path is not None and dependencies_path is not None:
            ecj_path = verify("ecj.jar", self_ecj_path)
            java_decompiler_path = verify("java-decompiler.jar", self_java_decompiler_path)
            if ecj_path is False or java_decompiler_path is False:
                sys.exit("请在当前目录存放ecj.jar、java-decompiler.jar，或者通过self_java_decompiler_path、self_ecj_path指定自定义路径")
            save_path = pathlib.Path.joinpath(pathlib.Path(app_path).parent,
                                              "{}_save_{}".format(pathlib.Path(app_path).name, int(time.time())))
            save_path.mkdir()
            java_decompiler_run()
            compile_cmd_file_create()
            create_database(app_path, include, save_path)
        elif app_path is not None:
            create_database(app_path, save_path)
        elif args.check is not None and app_path is not None and save_path is not None:
            procyon_path = verify("procyon.jar", self_procyon_path)
            if procyon_path is False:
                sys.exit("请在当前目录存放procyon.jar，或者通过self_procyon_path指定自定义路径")
            check()
        else:
            parse.print_help()
            sys.exit()
    else:
        if app_path is not None and dependencies_path is not None:
            ecj_path = verify("ecj.jar", self_ecj_path)
            java_decompiler_path = verify("java-decompiler.jar", self_java_decompiler_path)
            if ecj_path is False or java_decompiler_path is False:
                sys.exit("请在当前目录存放ecj.jar、java-decompiler.jar，或者通过self_java_decompiler_path、self_ecj_path指定自定义路径")
            save_path = pathlib.Path.joinpath(pathlib.Path(app_path).parent,
                                              "{}_save_{}".format(pathlib.Path(app_path).name, int(time.time())))
            save_path.mkdir()
            java_decompiler_run()
            compile_cmd_file_create()
        elif app_path is not None:
            create_database(app_path, save_path)
        elif args.check is not None and app_path is not None and save_path is not None:
            procyon_path = verify("procyon.jar", self_procyon_path)
            if procyon_path is False:
                sys.exit("请在当前目录存放procyon.jar，或者通过self_procyon_path指定自定义路径")
            check()
        else:
            parse.print_help()
            sys.exit()
