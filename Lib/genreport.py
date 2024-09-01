from PyLTSpice import RawRead
import plotly.graph_objects as go
import plotly.io as pio
import os
import base64
from PIL import Image
import screeninfo
import parse_ltspice_file

def png_to_hex_base64():
    imghexdata = ''
    img_path = "D:/4 WORKSPACE/FASTER/FASTER/assets/Circuit.png"
    screen = screeninfo.get_monitors()[0]
    screen_width, screen_height = screen.width, screen.height
    target_width = int(screen_width * 0.5)  
    target_height = int(screen_height * 0.4)  
    try:
        with Image.open(img_path) as img:
            resized_img = img.resize((target_width, target_height), resample=Image.LANCZOS)
            resized_img.save("img.png")
        img.close()
    except IOError:
        print("Unable to resize image")
    with open("img.png", "rb") as f:
        encoded_image = base64.b64encode(f.read())
    f.close()
    with open("image.txt", "w") as f:
        f.write(encoded_image.decode("utf-8"))
    f.close()
    with open("image.txt","r") as tempF:
        newlines = tempF.readlines()
        for singleline in newlines:
            imghexdata += singleline
    tempF.close()  
    if os.path.isfile("image.txt") and os.path.exists("image.txt"):
        os.remove("image.txt")
    if os.path.isfile("img.png") and os.path.exists("img.png"):
        os.remove("img.png")
    return imghexdata

def generate_report(raw_file_path,asc_file_path):
    LTR             = RawRead(raw_file_path)
    trace_names     = LTR.get_trace_names()
    print("Trace Names:", trace_names)
    time_trace_name = 'time'  
    time_trace      = LTR.get_trace(time_trace_name)
    traces          = {name: LTR.get_trace(name) for name in trace_names if name != time_trace_name}
    figs            = []

    for trace_name, trace in traces.items():
        steps       = LTR.get_steps()
        fig         = go.Figure()
        for step in range(len(steps)):
            x_data  = time_trace.get_wave(step)
            y_data  = trace.get_wave(step)
            fig.add_trace(go.Scatter(x=x_data, y=y_data, mode='lines', name=f'{trace_name} - {steps[step]}'))
        fig.update_layout(title=f'{trace_name}', xaxis_title='Time (s)', yaxis_title='Value')
        figs.append(fig)

    circuit_data    = parse_ltspice_file.parse_ltspice_file(asc_file_path)
    components      = circuit_data['components']
    component_names = [comp['name'] for comp in components]
    component_types = [comp['type'] for comp in components]
    component_values = [comp['value'] for comp in components]
    table_fig       = go.Figure(data=[go.Table(
        header      =dict(values=["Component Name", "Type", "Value"],
                    fill_color='paleturquoise',
                    align='left'),
        cells       =dict(values=[component_names, component_types, component_values],
                fill_color='lavender',
                align='left')
    )])
    title           = "LTSpice Analysis Report"
    html_content    = f"""
                        <!DOCTYPE html>
                        <html lang="en">
                        <head>
                            <meta charset="UTF-8">
                            <meta name="viewport" content="width=device-width, initial-scale=1.0">
                            <title>{title}</title>
                            <style>
                                .center {{ display: flex; justify-content: center; }}
                            </style>
                        </head>
                        <body>
                            <div class="center">
                                <img src="data:image/png;base64,{png_to_hex_base64()}" alt="flyback.png">
                            </div>
                            <h1>{title}</h1>
                        """
    for i, fig in enumerate(figs):
        fig_html = pio.to_html(fig, full_html=False)
        html_content += fig_html
    table_html = pio.to_html(table_fig, full_html=False)
    html_content += '<h2>Component Table</h2>'
    html_content += table_html
    html_content += '</body></html>'
    with open('D:/4 WORKSPACE/FASTER/FASTER/RES/ltspice_analysis_report.html', 'w', encoding='utf-8') as file:
        file.write(html_content)
    print('HTML report generated successfully!')