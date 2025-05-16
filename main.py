import os
import requests
from bs4 import BeautifulSoup
from ebooklib import epub
from urllib.parse import urljoin
from typing import List, Dict
import concurrent.futures
# ------------------- 配置区 --------------------
NOVEL_URL = "https://www.biquge321.com/xiaoshuo/508318/"
# ----------------------------------------------
def get_chapter_list(url: str) -> List[Dict]:
    """获取章节列表（标题和链接）"""
    try:
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'lxml')
        
        chapters = []
        chapter_container = soup.find('ul', class_='fen_4')
        print(chapter_container)
        if chapter_container:
            for a_tag in chapter_container.find_all('a'):
                if 'href' in a_tag.attrs:
                    chapters.append({
                        'title': a_tag.text.strip(),
                        'url': urljoin(url, a_tag['href'])
                    })
        return chapters  # 正式运行使用全部章节 
    except Exception as e:
        print(f"获取目录失败: {str(e)}")
        return []

def get_chapter_content(url: str) -> str:
    """获取单章正文内容（带重试机制）"""
    max_retries = 100  # 最大重试次数
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = requests.get(url, timeout=15)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 清理内容
            content_div = soup.find('div', id='txt')
            if content_div:
                # 移除广告链接等干扰元素
                for element in content_div.find_all(['a', 'script', 'style']):
                    element.decompose()
                # 处理换行
                for br in content_div.find_all('br'):
                    br.replace_with('\n')
                return content_div.get_text('\n', strip=True)
            return "本章内容获取失败"
        
        except Exception as e:
            retry_count += 1
            print(f"获取章节内容失败（第{retry_count}次重试）: {str(e)}")
            if retry_count == max_retries:
                print(f"已达到最大重试次数（{max_retries}次），放弃获取该章节")
    
    return "本章内容获取失败（多次尝试后失败）"

def generate_epub(chapters: List[Dict], filename: str) -> str:
    """生成EPUB电子书"""
    book = epub.EpubBook()
    
    # 元数据
    book.set_title("斗破苍穹")
    book.add_author("天蚕土豆")
    book.set_language('zh-CN')
    
    # 添加样式
    style = '''
    body { font-family: "Microsoft YaHei", sans-serif; font-size: 1em; line-height: 1.6; }
    h1 { font-size: 1.8em; border-bottom: 1px solid #ccc; padding-bottom: 0.5em; }
    '''
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", 
                           media_type="text/css", content=style)
    book.add_item(nav_css)
    
    # 添加章节
    spine = ['nav']
    for idx, chap in enumerate(chapters, 1):
        # 处理换行符
        processed_content = chap['content'].replace('\n', '</p><p>')
        
        chapter = epub.EpubHtml(
            title=chap['title'],
            file_name=f'chap_{idx}.xhtml',
            lang='zh'
        )
        chapter.content = f'''
        <h1>{chap['title']}</h1>    
        <p>{processed_content}</p>
        '''
        book.add_item(chapter)
        spine.append(chapter)
    
    # 生成目录结构
    book.toc = spine[1:]  # 排除nav
    book.spine = spine
    
    # 保存文件
    if not os.path.exists('books'):
        os.makedirs('books')
    epub_path = os.path.join('books', f'{filename}.epub')
    epub.write_epub(epub_path, book)
    return epub_path

if __name__ == "__main__":
    # 1. 获取章节列表
    print("正在获取章节列表...")
    all_chapters = get_chapter_list(NOVEL_URL)
    
    if not all_chapters:
        print("无有效章节，退出程序")
        exit()

    # 2. 多线程下载章节内容
    print(f"开始多线程爬取共 {len(all_chapters)} 章...")
    
    # 创建线程池（建议设置为5-10个线程）
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # 创建下载任务字典 {future: 章节索引}
        future_to_index = {
            executor.submit(get_chapter_content, chap['url']): idx 
            for idx, chap in enumerate(all_chapters)
        }

        # 实时显示下载进度
        for future in concurrent.futures.as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                content = future.result()
                all_chapters[idx]['content'] = content
                # 计算完成进度
                done_count = sum(1 for chap in all_chapters if 'content' in chap)
                print(f"\r下载进度: {done_count}/{len(all_chapters)} 章", end='')
            except Exception as e:
                print(f"\n章节 {all_chapters[idx]['title']} 下载失败: {str(e)}")
                all_chapters[idx]['content'] = "本章内容获取失败"

    # 3. 生成EPUB
    print("\n开始生成电子书...")
    epub_path = generate_epub(all_chapters, "斗破苍穹")
    print(f"电子书已生成到: {os.path.abspath(epub_path)}")