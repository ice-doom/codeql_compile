# codeql_compile
自动反编译闭源应用，创建codeql数据库



## 准备
首先下载[ecj.jar](https://mvnrepository.com/artifact/org.eclipse.jdt.core.compiler/ecj/4.6.1)和idea提供反编译的java-decompiler.jar，将其放置在脚本的相同目录中。


## 使用方法

1.在windows上使用
2.第二步不是必须项，可以直接执行第一步，然后就可以开始创建数据库
3.最好限制下要分析的包范围，过大反而不利于分析。

### 1、反编译项目
默认情况下使用java-decompiler.jar进行反编译

参数`-a`：指定项目源代码

参数`-d`：指定反编译代码的依赖包路径
```cmd
python3 codeql_compile.py -a D:\project\java\apps\2\cloud -d D:\project\java\apps\BOOT-INF\lib
```
执行后会在当前目录生成 *[项目名]_save_[时间戳]* 目录，该目录的run.cmd是编译代码的执行文件


### 2、校验反编译

对java-decompiler反编译的内容先编译一遍确认失败文件，再使用procyon反编译替换失败文件

先下载[procyon.jar](https://github.com/mstrobel/procyon/releases/download/0.6-prerelease/procyon-decompiler-0.6-prerelease.jar)，将其放置在脚本的相同目录中

参数`-o`：指定成功反编译代码存放的路径，即先前java-decompiler.jar反编译后的路径

参数`-c`：启用校验

```cmd
python3 codeql_compile.py -a D:\project\java\apps\2\cloud -o D:\project\java\apps\BOOT-INF\lib -c
```

### 3、使用codeql创建数据库

参数`--command`：指定生成的run.cmd
```cmd
D:\codeql.exe database create D:\codeql\databases\demo-database --language="java" --source-root=D:\codeql\demo_save_1641018608 --command="run.cmd"
```




