"""Paginate newly written content through the original subject styles."""
from copy import deepcopy
from compose import Composer,ROOT,command_bottom


def paginate(document, composer=None):
    composer = composer or Composer
    assert document.get('flow') is True and 'pages' not in document, 'Automatic flow takes one ordered blocks list'
    for block in document['blocks']:
        assert not any(k in block for k in ('column','top_mm')), 'Automatic flow assigns columns and page positions'
        assert block.get('gap_mm',0)>=0 and block.get('after_mm',0)>=0, 'Automatic flow requires nonnegative block spacing'
    settings={k:v for k,v in document.items() if k not in ('flow','blocks')}
    settings['auto_flow']=True
    final_page=0
    while True:
        pages=[];editor=None;column=1
        def advance():
            nonlocal editor,column,geometry,y
            if column==0:column=1
            else:
                column=0;editor=composer(document['subject'])
                page=settings|dict(page_no=len(pages)+1,last_page=len(pages)+1==final_page)
                geometry=editor.page_geometry(page);pages.append((editor,page))
            y=geometry['top'][column]
        geometry=None;y=0;advance()
        skipped=-1
        for index,original in enumerate(document['blocks']):
            if index<=skipped:continue
            if original.get('kind') in ('page_break', 'column_break'):
                if editor.commands or column:
                    advance()
                    if original['kind'] == 'page_break' and column:
                        advance()
                continue
            # A keep-with-next chain keeps the complete question together when it fits.
            if index+1<len(document['blocks']) and (original.get('keep_with_next') or
                original.get('number') and document['blocks'][index+1].get('kind')=='choices'):
                pair=[original,document['blocks'][index+1]]
                end_index=index+1
                while pair[-1].get('keep_with_next') and end_index+1<len(document['blocks']):
                    end_index+=1;pair.append(document['blocks'][end_index])
                # Oversized questions still keep their opening paragraph with the first object.
                groups=[pair] if len(pair)==2 else [pair,pair[:2]]
                for group,moved in ((g,m) for g in groups for m in (False,True)):
                    trial=composer(document['subject'])
                    if not moved:trial.float_regions=deepcopy(editor.float_regions)
                    target_column=(column+1)%2 if moved else column
                    target_page=pages[-1][1].copy()
                    if moved and target_column==0:
                        target_page.update(page_no=len(pages)+1,last_page=len(pages)+1==final_page)
                    target_top=trial.page_geometry(target_page)['top'][target_column] if moved else y
                    placed=[b|dict(column=target_column) for b in group]
                    placed[0]['top_mm']=target_top*25.4/7200
                    try:positions=trial.compose(target_page|dict(blocks=placed),write=False)
                    except AssertionError as error:
                        if 'exceeds the original' not in str(error):raise
                        continue
                    if moved:advance()
                    editor.commands.extend(trial.commands);editor.float_regions=trial.float_regions
                    y=positions[column];skipped=index+len(group)-1
                    break
                if skipped>=index:continue
            block=deepcopy(original);fragment={};attempts=0
            while True:
                start=len(editor.commands);regions=deepcopy(editor.float_regions)
                width=geometry['width'];x=geometry['left']+column*(width+geometry['gap'])
                top=y+block.get('gap_mm',0)*7200/25.4
                plain=block.get('kind') in (None,'paragraph') and not any(k in block for k in ('wrap_picture','wrap_table'))
                split_table=block.get('kind')=='table' and editor.can_split_table(block)
                if plain or block.get('kind')=='passage' or split_table:
                    fragment['bottom']=geometry['bottom'][column]
                    inset=block.get('left_mm',0)*7200/25.4
                    if plain:
                        end=editor.paragraph(block['runs'],block.get('style','question'),x+inset,top,width-inset,
                            number=block.get('number'),align=block.get('align'),para_shape=block.get('para_shape'),
                            number_suffix=block.get('number_suffix'),fragment=fragment,continued=block.get('continued',False),continues=block.get('continues',False))
                    elif split_table:end=editor.source_table(block,x+inset,top,width-inset,fragment=fragment)
                    else:end=editor.source_passage(block,x+inset,top,width-inset,fragment=fragment)
                    if fragment.get('tokens') or fragment.get('remaining'):
                        assert fragment['progress'] or attempts<3, 'A single text line or inline object cannot fit an empty original column'
                        attempts=0 if fragment['progress'] else attempts+1
                        block['gap_mm']=0;advance();continue
                    y=end+block.get('after_mm',0)*7200/25.4
                    break
                placed=block|dict(column=column,top_mm=top*25.4/7200,gap_mm=0)
                try:
                    positions=editor.compose(pages[-1][1]|dict(blocks=[placed]),write=False)
                except AssertionError as error:
                    del editor.commands[start:];editor.float_regions=regions
                    if 'exceeds the original' not in str(error):raise
                    assert attempts<3, 'This block is taller than an empty original column; split the table or passage'
                    attempts+=1;advance();continue
                y=positions[column];break
        while len(pages) < document.get('min_pages', 1):
            if column == 0:advance()
            advance()
        count=len(pages)
        # Reserve the final note once; relocating it must not oscillate between N and N+1 pages.
        if final_page:break
        final_page=count
    for i,(editor,page) in enumerate(pages,1):
        page['last_page']=i==count
        geometry=editor.page_geometry(page);divider=geometry['left']+geometry['width']+geometry['gap']/2
        assert all(command_bottom(c)<=geometry['bottom'][0 if c['x']<divider else 1]+1e-6 for c in editor.commands), 'Automatic flow crossed the original body boundary'
    return pages


def compose_flow(document,name):
    if 'sections' in document:
        assert document.get('flow') is True and not any(k in document for k in ('pages','blocks','elective')), 'Automatic sections need flow: true and their own blocks/elective settings'
        sections=document['sections']
        assert isinstance(sections,list) and sections, 'Provide at least one automatic section'
        defaults={k:v for k,v in document.items() if k!='sections'}
        pages=[]
        for section in sections:
            assert isinstance(section,dict) and isinstance(section.get('blocks'),list), 'Each automatic section needs a blocks array'
            assert not any(k in section for k in ('subject','flow','sections','pages')), 'Sections share the document subject and automatic flow'
            pages.extend(paginate(defaults|section))
    else:pages=paginate(document)
    count=len(pages)
    source='#import "../exam.typ": *\n#import "../original-header.typ": source-commands\n'
    for i,(editor,page) in enumerate(pages,1):
        source+=editor.compose(page|dict(total=count,footer_no=i,blocks=[]),f'{name}-{i}')
    path=ROOT/f'generated/{name}.typ';path.write_text(source,encoding='utf-8')
    return path,count
