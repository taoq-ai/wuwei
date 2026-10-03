"""Generate docs/site/assets/hero-dark.svg and hero-light.svg from one geometry.

Path lengths set the token timings, so edit the drawing here, then run
`python3 scripts/build-hero.py` and commit both files. A test checks they match.
"""
import math, sys
from pathlib import Path

T = 18.0          # one cycle, seconds
V = 150.0         # travel speed, viewBox units per second
EASE = '0.3 0 0.7 1'
LIN = '0 0 1 1'

PAL = {
    'dark': dict(bg='#102622', panel='#193B35', text='#ECF8F5', muted='#B1CBC4', accent='#00C9A7',
                 atext='#00C9A7', warm='#F2B65E', coral='#FF8C7A', shadow='#000000', core='#ECF8F5'),
    'light': dict(bg='#F4FAF8', panel='#FFFFFF', text='#183B37', muted='#42615C', accent='#00C9A7',
                  atext='#00735F', warm='#935600', coral='#B73A28', shadow='#6E918A', core='#00806B'),
}

# Simple Icons 16.33.0 (CC0-1.0, https://github.com/simple-icons/simple-icons): 24x24 path data
ICONS = {
    'linear': 'M2.886 4.18A11.982 11.982 0 0 1 11.99 0C18.624 0 24 5.376 24 12.009c0 3.64-1.62 6.903-4.18 9.105L2.887 4.18ZM1.817 5.626l16.556 16.556c-.524.33-1.075.62-1.65.866L.951 7.277c.247-.575.537-1.126.866-1.65ZM.322 9.163l14.515 14.515c-.71.172-1.443.282-2.195.322L0 11.358a12 12 0 0 1 .322-2.195Zm-.17 4.862 9.823 9.824a12.02 12.02 0 0 1-9.824-9.824Z',
    'jira': 'M11.571 11.513H0a5.218 5.218 0 0 0 5.232 5.215h2.13v2.057A5.215 5.215 0 0 0 12.575 24V12.518a1.005 1.005 0 0 0-1.005-1.005zm5.723-5.756H5.736a5.215 5.215 0 0 0 5.215 5.214h2.129v2.058a5.218 5.218 0 0 0 5.215 5.214V6.758a1.001 1.001 0 0 0-1.001-1.001zM23.013 0H11.455a5.215 5.215 0 0 0 5.215 5.215h2.129v2.057A5.215 5.215 0 0 0 24 12.483V1.005A1.001 1.001 0 0 0 23.013 0Z',
    'github': 'M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12',
    'claude': 'm4.7144 15.9555 4.7174-2.6471.079-.2307-.079-.1275h-.2307l-.7893-.0486-2.6956-.0729-2.3375-.0971-2.2646-.1214-.5707-.1215-.5343-.7042.0546-.3522.4797-.3218.686.0608 1.5179.1032 2.2767.1578 1.6514.0972 2.4468.255h.3886l.0546-.1579-.1336-.0971-.1032-.0972L6.973 9.8356l-2.55-1.6879-1.3356-.9714-.7225-.4918-.3643-.4614-.1578-1.0078.6557-.7225.8803.0607.2246.0607.8925.686 1.9064 1.4754 2.4893 1.8336.3643.3035.1457-.1032.0182-.0728-.164-.2733-1.3539-2.4467-1.445-2.4893-.6435-1.032-.17-.6194c-.0607-.255-.1032-.4674-.1032-.7285L6.287.1335 6.6997 0l.9957.1336.419.3642.6192 1.4147 1.0018 2.2282 1.5543 3.0296.4553.8985.2429.8318.091.255h.1579v-.1457l.1275-1.706.2368-2.0947.2307-2.6957.0789-.7589.3764-.9107.7468-.4918.5828.2793.4797.686-.0668.4433-.2853 1.8517-.5586 2.9021-.3643 1.9429h.2125l.2429-.2429.9835-1.3053 1.6514-2.0643.7286-.8196.85-.9046.5464-.4311h1.0321l.759 1.1293-.34 1.1657-1.0625 1.3478-.8804 1.1414-1.2628 1.7-.7893 1.36.0729.1093.1882-.0183 2.8535-.607 1.5421-.2794 1.8396-.3157.8318.3886.091.3946-.3278.8075-1.967.4857-2.3072.4614-3.4364.8136-.0425.0304.0486.0607 1.5482.1457.6618.0364h1.621l3.0175.2247.7892.522.4736.6376-.079.4857-1.2142.6193-1.6393-.3886-3.825-.9107-1.3113-.3279h-.1822v.1093l1.0929 1.0686 2.0035 1.8092 2.5075 2.3314.1275.5768-.3218.4554-.34-.0486-2.2039-1.6575-.85-.7468-1.9246-1.621h-.1275v.17l.4432.6496 2.3436 3.5214.1214 1.0807-.17.3521-.6071.2125-.6679-.1214-1.3721-1.9246L14.38 17.959l-1.1414-1.9428-.1397.079-.674 7.2552-.3156.3703-.7286.2793-.6071-.4614-.3218-.7468.3218-1.4753.3886-1.9246.3157-1.53.2853-1.9004.17-.6314-.0121-.0425-.1397.0182-1.4328 1.9672-2.1796 2.9446-1.7243 1.8456-.4128.164-.7164-.3704.0667-.6618.4008-.5889 2.386-3.0357 1.4389-1.882.929-1.0868-.0062-.1579h-.0546l-6.3385 4.1164-1.1293.1457-.4857-.4554.0608-.7467.2307-.2429 1.9064-1.3114Z',
    'pytest': 'M2.6152 0v.8867h3.8399V0zm5.0215 0v.8867h3.8418V0zm4.957 0v.8867h3.8418V0zm4.9356 0v.8867h3.8418V0zM2.4473 1.8945a.935.935 0 0 0-.9356.9356c0 .517.4185.9375.9356.9375h19.1054c.5171 0 .9356-.4204.9356-.9375a.935.935 0 0 0-.9356-.9356zm.168 2.8477V24H6.455V4.7422zm5.0214 0V20.543h3.8418V4.7422zm4.957 0V15.291h3.8497V4.7422zm4.9356 0v6.4941h3.8418V4.7422z',
    'gitlab': 'm23.6004 9.5927-.0337-.0862L20.3.9814a.851.851 0 0 0-.3362-.405.8748.8748 0 0 0-.9997.0539.8748.8748 0 0 0-.29.4399l-2.2055 6.748H7.5375l-2.2057-6.748a.8573.8573 0 0 0-.29-.4412.8748.8748 0 0 0-.9997-.0537.8585.8585 0 0 0-.3362.4049L.4332 9.5015l-.0325.0862a6.0657 6.0657 0 0 0 2.0119 7.0105l.0113.0087.03.0213 4.976 3.7264 2.462 1.8633 1.4995 1.1321a1.0085 1.0085 0 0 0 1.2197 0l1.4995-1.1321 2.4619-1.8633 5.006-3.7489.0125-.01a6.0682 6.0682 0 0 0 2.0094-7.003z',
    'notion': 'M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.968c-.42-.326-.981-.7-2.055-.607L3.01 2.295c-.466.046-.56.28-.374.466zm.793 3.08v13.904c0 .747.373 1.027 1.214.98l14.523-.84c.841-.046.935-.56.935-1.167V6.354c0-.606-.233-.933-.748-.887l-15.177.887c-.56.047-.747.327-.747.933zm14.337.745c.093.42 0 .84-.42.888l-.7.14v10.264c-.608.327-1.168.514-1.635.514-.748 0-.935-.234-1.495-.933l-4.577-7.186v6.952L12.21 19s0 .84-1.168.84l-3.222.186c-.093-.186 0-.653.327-.746l.84-.233V9.854L7.822 9.76c-.094-.42.14-1.026.793-1.073l3.456-.233 4.764 7.279v-6.44l-1.215-.139c-.093-.514.28-.887.747-.933zM1.936 1.035l13.31-.98c1.634-.14 2.055-.047 3.082.7l4.249 2.986c.7.513.934.653.934 1.213v16.378c0 1.026-.373 1.634-1.68 1.726l-15.458.934c-.98.047-1.448-.093-1.962-.747l-3.129-4.06c-.56-.747-.793-1.306-.793-1.96V2.667c0-.839.374-1.54 1.447-1.632z',
    'confluence': 'M.87 18.257c-.248.382-.53.875-.763 1.245a.764.764 0 0 0 .255 1.04l4.965 3.054a.764.764 0 0 0 1.058-.26c.199-.332.454-.763.733-1.221 1.967-3.247 3.945-2.853 7.508-1.146l4.957 2.337a.764.764 0 0 0 1.028-.382l2.364-5.346a.764.764 0 0 0-.382-1 599.851 599.851 0 0 1-4.965-2.361C10.911 10.97 5.224 11.185.87 18.257zM23.131 5.743c.249-.405.531-.875.764-1.25a.764.764 0 0 0-.256-1.034L18.675.404a.764.764 0 0 0-1.058.26c-.195.335-.451.763-.734 1.225-1.966 3.246-3.945 2.85-7.508 1.146L4.437.694a.764.764 0 0 0-1.027.382L1.046 6.422a.764.764 0 0 0 .382 1c1.039.49 3.105 1.467 4.965 2.361 6.698 3.246 12.392 3.029 16.738-4.04z',
    'markdown': 'M22.27 19.385H1.73A1.73 1.73 0 010 17.655V6.345a1.73 1.73 0 011.73-1.73h20.54A1.73 1.73 0 0124 6.345v11.308a1.73 1.73 0 01-1.73 1.731zM5.769 15.923v-4.5l2.308 2.885 2.307-2.885v4.5h2.308V8.078h-2.308l-2.307 2.885-2.308-2.885H3.46v7.847zM21.232 12h-2.309V8.077h-2.307V12h-2.308l3.461 4.039z',
    'discord': 'M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z',
    'pagerduty': 'M16.965 1.18C15.085.164 13.769 0 10.683 0H3.73v14.55h6.926c2.743 0 4.8-.164 6.61-1.37 1.975-1.303 3.004-3.484 3.004-6.007 0-2.716-1.262-4.896-3.305-5.994zm-5.5 10.326h-4.21V3.113l3.977-.027c3.62-.028 5.43 1.234 5.43 4.128 0 3.113-2.248 4.292-5.197 4.292zM3.73 17.61h3.525V24H3.73Z',
    'grafana': 'M23.02 10.59a8.578 8.578 0 0 0-.862-3.034 8.911 8.911 0 0 0-1.789-2.445c.337-1.342-.413-2.505-.413-2.505-1.292-.08-2.113.4-2.416.62-.052-.02-.102-.044-.154-.064-.22-.089-.446-.172-.677-.247-.231-.073-.47-.14-.711-.197a9.867 9.867 0 0 0-.875-.161C14.557.753 12.94 0 12.94 0c-1.804 1.145-2.147 2.744-2.147 2.744l-.018.093c-.098.029-.2.057-.298.088-.138.042-.275.094-.413.143-.138.055-.275.107-.41.166a8.869 8.869 0 0 0-1.557.87l-.063-.029c-2.497-.955-4.716.195-4.716.195-.203 2.658.996 4.33 1.235 4.636a11.608 11.608 0 0 0-.607 2.635C1.636 12.677.953 15.014.953 15.014c1.926 2.214 4.171 2.351 4.171 2.351.003-.002.006-.002.006-.005.285.509.615.994.986 1.446.156.19.32.371.488.548-.704 2.009.099 3.68.099 3.68 2.144.08 3.553-.937 3.849-1.173a9.784 9.784 0 0 0 3.164.501h.08l.055-.003.107-.002.103-.005.003.002c1.01 1.44 2.788 1.646 2.788 1.646 1.264-1.332 1.337-2.653 1.337-2.94v-.058c0-.02-.003-.039-.003-.06.265-.187.52-.387.758-.6a7.875 7.875 0 0 0 1.415-1.7c1.43.083 2.437-.885 2.437-.885-.236-1.49-1.085-2.216-1.264-2.354l-.018-.013-.016-.013a.217.217 0 0 1-.031-.02c.008-.092.016-.18.02-.27.011-.162.016-.323.016-.48v-.253l-.005-.098-.008-.135a1.891 1.891 0 0 0-.01-.13c-.003-.042-.008-.083-.013-.125l-.016-.124-.018-.122a6.215 6.215 0 0 0-2.032-3.73 6.015 6.015 0 0 0-3.222-1.46 6.292 6.292 0 0 0-.85-.048l-.107.002h-.063l-.044.003-.104.008a4.777 4.777 0 0 0-3.335 1.695c-.332.4-.592.84-.768 1.297a4.594 4.594 0 0 0-.312 1.817l.003.091c.005.055.007.11.013.164a3.615 3.615 0 0 0 .698 1.82 3.53 3.53 0 0 0 1.827 1.282c.33.098.66.14.971.137.039 0 .078 0 .114-.002l.063-.003c.02 0 .041-.003.062-.003.034-.002.065-.007.099-.01.007 0 .018-.003.028-.003l.031-.005.06-.008a1.18 1.18 0 0 0 .112-.02c.036-.008.072-.013.109-.024a2.634 2.634 0 0 0 .914-.415c.028-.02.056-.041.085-.065a.248.248 0 0 0 .039-.35.244.244 0 0 0-.309-.06l-.078.042c-.09.044-.184.083-.283.116a2.476 2.476 0 0 1-.475.096c-.028.003-.054.006-.083.006l-.083.002c-.026 0-.054 0-.08-.002l-.102-.006h-.012l-.024.006c-.016-.003-.031-.003-.044-.006-.031-.002-.06-.007-.091-.01a2.59 2.59 0 0 1-.724-.213 2.557 2.557 0 0 1-.667-.438 2.52 2.52 0 0 1-.805-1.475 2.306 2.306 0 0 1-.029-.444l.006-.122v-.023l.002-.031c.003-.021.003-.04.005-.06a3.163 3.163 0 0 1 1.352-2.29 3.12 3.12 0 0 1 .937-.43 2.946 2.946 0 0 1 .776-.101h.06l.07.002.045.003h.026l.07.005a4.041 4.041 0 0 1 1.635.49 3.94 3.94 0 0 1 1.602 1.662 3.77 3.77 0 0 1 .397 1.414l.005.076.003.075c.002.026.002.05.002.075 0 .024.003.052 0 .07v.065l-.002.073-.008.174a6.195 6.195 0 0 1-.08.639 5.1 5.1 0 0 1-.267.927 5.31 5.31 0 0 1-.624 1.13 5.052 5.052 0 0 1-3.237 2.014 4.82 4.82 0 0 1-.649.066l-.039.003h-.287a6.607 6.607 0 0 1-1.716-.265 6.776 6.776 0 0 1-3.4-2.274 6.75 6.75 0 0 1-.746-1.15 6.616 6.616 0 0 1-.714-2.596l-.005-.083-.002-.02v-.056l-.003-.073v-.096l-.003-.104v-.07l.003-.163c.008-.22.026-.45.054-.678a8.707 8.707 0 0 1 .28-1.355c.128-.444.286-.872.473-1.277a7.04 7.04 0 0 1 1.456-2.1 5.925 5.925 0 0 1 .953-.763c.169-.111.343-.213.524-.306.089-.05.182-.091.273-.135.047-.02.093-.042.138-.062a7.177 7.177 0 0 1 .714-.267l.145-.045c.049-.015.098-.026.148-.041.098-.029.197-.052.296-.076.049-.013.1-.02.15-.033l.15-.032.151-.028.076-.013.075-.01.153-.024c.057-.01.114-.013.171-.023l.169-.021c.036-.003.073-.008.106-.01l.073-.008.036-.003.042-.002c.057-.003.114-.008.171-.01l.086-.006h.023l.037-.003.145-.007a7.999 7.999 0 0 1 1.708.125 7.917 7.917 0 0 1 2.048.68 8.253 8.253 0 0 1 1.672 1.09l.09.077.089.078c.06.052.114.107.171.159.057.052.112.106.166.16.052.055.107.107.159.164a8.671 8.671 0 0 1 1.41 1.978c.012.026.028.052.04.078l.04.078.075.156c.023.051.05.1.07.153l.065.15a8.848 8.848 0 0 1 .45 1.34.19.19 0 0 0 .201.142.186.186 0 0 0 .172-.184c.01-.246.002-.532-.024-.856z',
    'sentry': 'M13.91 2.505c-.873-1.448-2.972-1.448-3.844 0L6.904 7.92a15.478 15.478 0 0 1 8.53 12.811h-2.221A13.301 13.301 0 0 0 5.784 9.814l-2.926 5.06a7.65 7.65 0 0 1 4.435 5.848H2.194a.365.365 0 0 1-.298-.534l1.413-2.402a5.16 5.16 0 0 0-1.614-.913L.296 19.275a2.182 2.182 0 0 0 .812 2.999 2.24 2.24 0 0 0 1.086.288h6.983a9.322 9.322 0 0 0-3.845-8.318l1.11-1.922a11.47 11.47 0 0 1 4.95 10.24h5.915a17.242 17.242 0 0 0-7.885-15.28l2.244-3.845a.37.37 0 0 1 .504-.13c.255.14 9.75 16.708 9.928 16.9a.365.365 0 0 1-.327.543h-2.287c.029.612.029 1.223 0 1.831h2.297a2.206 2.206 0 0 0 1.922-3.31z',
    'datadog': 'M19.57 17.04l-1.997-1.316-1.665 2.782-1.937-.567-1.706 2.604.087.82 9.274-1.71-.538-5.794zm-8.649-2.498l1.488-.204c.241.108.409.15.697.223.45.117.97.23 1.741-.16.18-.088.553-.43.704-.625l6.096-1.106.622 7.527-10.444 1.882zm11.325-2.712l-.602.115L20.488 0 .789 2.285l2.427 19.693 2.306-.334c-.184-.263-.471-.581-.96-.989-.68-.564-.44-1.522-.039-2.127.53-1.022 3.26-2.322 3.106-3.956-.056-.594-.15-1.368-.702-1.898-.02.22.017.432.017.432s-.227-.289-.34-.683c-.112-.15-.2-.199-.319-.4-.085.233-.073.503-.073.503s-.186-.437-.216-.807c-.11.166-.137.48-.137.48s-.241-.69-.186-1.062c-.11-.323-.436-.965-.343-2.424.6.421 1.924.321 2.44-.439.171-.251.288-.939-.086-2.293-.24-.868-.835-2.16-1.066-2.651l-.028.02c.122.395.374 1.223.47 1.625.293 1.218.372 1.642.234 2.204-.116.488-.397.808-1.107 1.165-.71.358-1.653-.514-1.713-.562-.69-.55-1.224-1.447-1.284-1.883-.062-.477.275-.763.445-1.153-.243.07-.514.192-.514.192s.323-.334.722-.624c.165-.109.262-.178.436-.323a9.762 9.762 0 0 0-.456.003s.42-.227.855-.392c-.318-.014-.623-.003-.623-.003s.937-.419 1.678-.727c.509-.208 1.006-.147 1.286.257.367.53.752.817 1.569.996.501-.223.653-.337 1.284-.509.554-.61.99-.688.99-.688s-.216.198-.274.51c.314-.249.66-.455.66-.455s-.134.164-.259.426l.03.043c.366-.22.797-.394.797-.394s-.123.156-.268.358c.277-.002.838.012 1.056.037 1.285.028 1.552-1.374 2.045-1.55.618-.22.894-.353 1.947.68.903.888 1.609 2.477 1.259 2.833-.294.295-.874-.115-1.516-.916a3.466 3.466 0 0 1-.716-1.562 1.533 1.533 0 0 0-.497-.85s.23.51.23.96c0 .246.03 1.165.424 1.68-.039.076-.057.374-.1.43-.458-.554-1.443-.95-1.604-1.067.544.445 1.793 1.468 2.273 2.449.453.927.186 1.777.416 1.997.065.063.976 1.197 1.15 1.767.306.994.019 2.038-.381 2.685l-1.117.174c-.163-.045-.273-.068-.42-.153.08-.143.241-.5.243-.572l-.063-.111c-.348.492-.93.97-1.414 1.245-.633.359-1.363.304-1.838.156-1.348-.415-2.623-1.327-2.93-1.566 0 0-.01.191.048.234.34.383 1.119 1.077 1.872 1.56l-1.605.177.759 5.908c-.337.048-.39.071-.757.124-.325-1.147-.946-1.895-1.624-2.332-.599-.384-1.424-.47-2.214-.314l-.05.059a2.851 2.851 0 0 1 1.863.444c.654.413 1.181 1.481 1.375 2.124.248.822.42 1.7-.248 2.632-.476.662-1.864 1.028-2.986.237.3.481.705.876 1.25.95.809.11 1.577-.03 2.106-.574.452-.464.69-1.434.628-2.456l.714-.104.258 1.834 11.827-1.424zM15.05 6.848c-.034.075-.085.125-.007.37l.004.014.013.032.032.073c.14.287.295.558.552.696.067-.011.136-.019.207-.023.242-.01.395.028.492.08.009-.048.01-.119.005-.222-.018-.364.072-.982-.626-1.308-.264-.122-.634-.084-.757.068a.302.302 0 0 1 .058.013c.186.066.06.13.027.207m1.958 3.392c-.092-.05-.52-.03-.821.005-.574.068-1.193.267-1.328.372-.247.191-.135.523.047.66.511.382.96.638 1.432.575.29-.038.546-.497.728-.914.124-.288.124-.598-.058-.698m-5.077-2.942c.162-.154-.805-.355-1.556.156-.554.378-.571 1.187-.041 1.646.053.046.096.078.137.104a4.77 4.77 0 0 1 1.396-.412c.113-.125.243-.345.21-.745-.044-.542-.455-.456-.146-.749',
}

# Tools per row, one source for the drawing, the alt text and the shipped-versus-planned test.
# (row caption, row centre, [(name, label, glyph, proof, issue)]): glyph is an ICONS key or a
# two-letter badge; proof is the repository path that shows the tool ships, None when planned;
# issue is the issue that will ship a planned tool, or None. Rows sharing a centre alternate.
ROWS = [
    ('Plan tracker', (124, 262), [
        ('Linear', 'Linear', 'linear', 'adapters/tracker/linear.py', None),
        ('Jira', 'Jira', 'jira', None, '#417'),
        ('GitHub Projects', 'Projects', 'github', None, '#417')]),
    ('Plan spec engine', (124, 262), [
        ('spec-kit', 'spec-kit', 'SK', None, '#412'),
        ('superpowers', 'superpowers', 'SP', None, '#412'),
        ('OpenSpec', 'OpenSpec', 'OS', None, '#412')]),
    ('Build runtime', (365, 282), [
        ('Claude Code', 'Claude', 'claude', 'adapters/runtime/claude.py', None),
        ('Codex', 'Codex', 'CX', 'adapters/runtime/codex.py', None)]),
    ('Review gate tools', (722, 150), [
        ('ZIRAN', 'ZIRAN', 'ZI', 'adapters/scanner/ziran.py', None),
        ('pytest', 'pytest', 'pytest', 'cli/wuwei/calibrate.py', None)]),
    ('Close code host', (1115, 418), [
        ('GitHub', 'GitHub', 'github', 'adapters/code_host/github.py', None),
        ('GitLab', 'GitLab', 'gitlab', None, '#370')]),
    ('Close docs', (1068, 552), [
        ('Notion', 'Notion', 'notion', None, '#419'),
        ('Confluence', 'Confluence', 'confluence', None, '#419'),
        ('Markdown', 'Markdown', 'markdown', None, '#419')]),
    ('Phone and DM', (378, 372), [
        ('Slack', 'Slack', 'SL', 'adapters/chat/slack.py', None),
        ('Claude mobile', 'Mobile', 'claude', 'cli/wuwei/control_plane.py', None),
        ('Teams', 'Teams', 'TE', None, None),
        ('Discord', 'Discord', 'discord', None, None)]),
    ('On-call', (1050, 70), [
        ('PagerDuty', 'PagerDuty', 'pagerduty', None, '#415'),
        ('Grafana', 'Grafana', 'grafana', None, '#415'),
        ('Sentry', 'Sentry', 'sentry', None, '#415'),
        ('Datadog', 'Datadog', 'datadog', None, '#415')]),
]
PITCH = 60

# ---- geometry helpers -------------------------------------------------------
def bez(p0, p1, p2, p3, t):
    u = 1 - t
    return tuple(u**3*a + 3*u*u*t*b + 3*u*t*t*c + t**3*d for a, b, c, d in zip(p0, p1, p2, p3))

def blen(p0, p1, p2, p3, n=200):
    pts = [bez(p0, p1, p2, p3, i/n) for i in range(n+1)]
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))

def split(p0, p1, p2, p3, t):
    """Return the second part of a cubic split at t."""
    lerp = lambda a, b: tuple(x + (y-x)*t for x, y in zip(a, b))
    a, b, c = lerp(p0, p1), lerp(p1, p2), lerp(p2, p3)
    d, e = lerp(a, b), lerp(b, c)
    f = lerp(d, e)
    return f, e, c, p3

f = lambda p: f'{p[0]:g} {p[1]:g}'

class Seg:
    """A path fragment without its M, plus start, end and length."""
    def __init__(self, d, start, end, length):
        self.d, self.start, self.end, self.length = d, start, end, length

def C(p0, c1, c2, p1):
    return Seg(f'C {f(c1)}, {f(c2)}, {f(p1)}', p0, p1, blen(p0, c1, c2, p1))

def L(p0, p1):
    return Seg(f'L {f(p1)}', p0, p1, math.dist(p0, p1))

def A(p0, p1, r, angle):
    return Seg(f'A {r} {r} 0 0 1 {f(p1)}', p0, p1, r*angle)

def path(*segs):
    return f'M {f(segs[0].start)} ' + ' '.join(s.d for s in segs)

def cat(*segs):
    d = ' '.join(s.d for s in segs)
    return Seg(d, segs[0].start, segs[-1].end, sum(s.length for s in segs))

# ---- layout -----------------------------------------------------------------
P, B, R, J = (180, 385), (455, 210), (730, 210), (965, 210)
OC, OR = (1052, 345), 36                     # shepherd orbit
OT, OB = (OC[0], OC[1]-OR), (OC[0], OC[1]+OR)
CL = (990, 488)
KC, KR = (455, 300), 30                       # build and check loop
KT, KB = (KC[0], KC[1]-KR), (KC[0], KC[1]+KR)
LANE = 62                                     # gate lane offset
GX = 882                                      # gate marker x
RX = R[0] + 75                                # Review right edge

pb_ctrl = (P, (180, 285), (330, 210), B)
seg_pb = C(*pb_ctrl)
seg_br = L(B, R)
seg_rj = L(R, J)
seg_jo = C(J, (1022, 210), (OT[0], 255), OT)
seg_ohalf = A(OT, OB, OR, math.pi)
seg_ofull = cat(A(OT, OB, OR, math.pi), A(OB, OT, OR, math.pi))
seg_oc = C(OB, (OB[0], 445), (1040, CL[1]), CL)
seg_mem = C(CL, (905, 585), (310, 590), P)
seg_check = cat(L(B, KT), A(KT, KB, KR, math.pi), A(KB, KT, KR, math.pi), L(KT, B))
fix_a = C(J, (1009, 140), (979, 96), (895, 96))
fix_b = L((895, 96), (565, 96))
fix_c = C((565, 96), (522, 96), (505, 132), (505, 182))
seg_fix = cat(fix_a, fix_b, fix_c, L((505, 182), B))
SW0 = (262, 172)
join = split(*pb_ctrl, 0.72)
seg_sweep = cat(C(SW0, (305, 172), (330, 192), join[0]), C(*join))

def lane(dy):
    y = R[1] + dy
    return cat(L(R, (RX, R[1])), C((RX, R[1]), (RX+40, R[1]), (GX-45, y), (GX, y)),
               C((GX, y), (GX+45, y), (J[0]-40, R[1]), J))
lane_top, lane_mid, lane_bot = lane(-LANE), seg_rj, lane(LANE)

def until_box(p0, c1, c2, p3, c, w, h=56):
    """Cubic cut where it first enters the node box centred at c."""
    t = next(i/400 for i in range(401) if abs(bez(p0, c1, c2, p3, i/400)[0]-c[0]) <= w/2+6
             and abs(bez(p0, c1, c2, p3, i/400)[1]-c[1]) <= h/2+6)
    lerp = lambda a, b: tuple(x + (y-x)*t for x, y in zip(a, b))
    a, b, cc = lerp(p0, c1), lerp(c1, c2), lerp(c2, p3)
    d, e = lerp(a, b), lerp(b, cc)
    return f'M {f(p0)} C {f(a)}, {f(d)}, {f(lerp(d, e))}'
arrow_mem = until_box(CL, (905, 585), (310, 590), P, P, 136)
arrow_close = until_box(OB, (OB[0], 445), (1040, CL[1]), CL, CL, 136)

# ---- token timelines --------------------------------------------------------
class Tok:
    def __init__(self, start):
        self.segs, self.keys, self.t, self.start = [], [(0.0, 0.0)], 0.0, start
        self.events, self.dist = {}, 0.0
    def move(self, seg, name=None, speed=V):
        self.segs.append(seg)
        self.dist += seg.length
        self.t += seg.length / speed
        self.keys.append((self.t, self.dist))
        if name: self.events[name] = self.t
        return self
    def wait(self, s, name=None):
        if name: self.events[name] = self.t
        self.t += s
        self.keys.append((self.t, self.dist))
        return self
    def mark(self, name):
        self.events[name] = self.t
        return self

def pct(x): return f'{x:.4f}'.rstrip('0').rstrip('.') or '0'

def motion(tok):
    """animateMotion for a token; local timeline padded to T."""
    assert tok.t <= T - 0.3, tok.t
    keys = tok.keys + [(T, tok.dist)]
    kt = ';'.join(pct(t/T) for t, _ in keys)
    kp = ';'.join(pct(d/tok.dist) for _, d in keys)
    ks = ';'.join(EASE if b[1] > a[1] else LIN for a, b in zip(keys, keys[1:]))
    d = path(*tok.segs)
    return (f'<animateMotion dur="{T:g}s" begin="{-tok.start:g}s" repeatCount="indefinite" calcMode="spline" '
            f'keyTimes="{kt}" keyPoints="{kp}" keySplines="{ks}" path="{d}"/>')

def window(times, values, begin, attr='opacity', calc='linear'):
    """Animate attr through values at local times (seconds), padded to 0 and T."""
    times, values = list(times), list(values)
    if times[0] > 0: times, values = [0] + times, [values[0]] + values
    if times[-1] < T: times, values = times + [T], values + [values[-1]]
    assert times == sorted(times) and 0 <= times[0] and times[-1] <= T, times
    return (f'<animate attributeName="{attr}" dur="{T:g}s" begin="{-begin:g}s" repeatCount="indefinite" '
            f'calcMode="{calc}" keyTimes="{";".join(pct(t/T) for t in times)}" values="{";".join(values)}"/>')

def fade(tok, t_in, t_out):
    return window([t_in, t_in + 0.5, t_out - 0.5, t_out], ['0', '1', '1', '0'], tok.start)

# A: build and check loop. B: three gates. C: FIX round. D: sweep and shepherd orbit.
A_ = Tok(start=0.0).wait(0.8).mark('gate').move(seg_pb).wait(0.3).move(seg_check, speed=110).wait(0.3) \
    .move(seg_br).wait(0.4).move(seg_rj).wait(0.3).move(cat(seg_jo, seg_ohalf, seg_oc)).mark('close').wait(0.8)
B_ = Tok(start=13.5).wait(0.6).move(seg_pb).wait(0.3).move(seg_br).mark('review').wait(0.6)
b_rj0 = B_.t
B_.move(seg_rj, speed=V*0.75)
b_rj1 = B_.t
B_.wait(0.4).move(cat(seg_jo, seg_ohalf, seg_oc)).wait(0.8)
C_ = Tok(start=5.0).wait(0.5).move(seg_br).wait(0.3).move(seg_rj).wait(0.4)  # emerges from Build
c_fix0 = C_.t
C_.move(seg_fix).wait(0.3)
c_fix1 = C_.t
C_.move(seg_br).wait(0.2).move(seg_rj).wait(0.3).move(cat(seg_jo, seg_ohalf, seg_oc)).wait(0.5)
D_ = Tok(start=9.0).wait(0.4).move(seg_sweep).wait(0.3).move(seg_br).wait(0.3).move(seg_rj).wait(0.3) \
    .move(seg_jo).move(seg_ofull, speed=90).move(seg_ohalf, 'merge').wait(0.6).move(seg_oc).wait(0.8)
MEM = Tok(start=0.0).move(seg_mem, speed=V*0.8)
MEM.start = (A_.start - MEM.t) % T      # memory reaches Plan as A leaves the morning gate
for name, tok in zip('ABCDM', (A_, B_, C_, D_, MEM)):
    print(name, f'{tok.t:.2f}s', f'{tok.dist:.0f}u', file=sys.stderr)

# ---- SVG --------------------------------------------------------------------
FONT = "font-family=\"-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif\""

def token(tok, extra='', core='core'):
    return (f'<g class="tok" opacity="0">{fade(tok, 0, tok.t)}{motion(tok)}'
            f'<circle r="22" fill="url(#glow)"/><circle r="7" fill="{{{core}}}" stroke="{{accent}}" stroke-width="3">{extra}</circle></g>')

def ghost(seg, tok, t0, t1):
    keys = [0, t0, t1, T]
    kt = ';'.join(pct(t/T) for t in keys)
    return (f'<g class="tok" opacity="0">'
            + window([t0 - 0.2, t0, t1, t1 + 0.2], ['0', '1', '1', '0'], tok.start)
            + f'<animateMotion dur="{T:g}s" begin="{-tok.start:g}s" repeatCount="indefinite" calcMode="spline" '
              f'keyTimes="{kt}" keyPoints="0;0;1;1" keySplines="{LIN};{EASE};{LIN}" path="{path(seg)}"/>'
            f'<circle r="22" fill="url(#glow)"/><circle r="7" fill="{{core}}" stroke="{{accent}}" stroke-width="3"/></g>')

def pulse(d, tok, t):
    return (f'<path class="pulse" d="{d}" fill="none" stroke="{{warm}}" stroke-width="3" opacity="0">'
            + window([t - 0.1, t + 0.4, t + 1.2, t + 2.4], ['0', '0.9', '0.9', '0'], tok.start) + '</path>')

def shield(x, y):
    return f'<use href="#shield" x="{x}" y="{y}"/>'

def xs(tools):
    pitch = max([PITCH] + [3.4 * (len(a[1]) + len(b[1])) + 8 for a, b in zip(tools, tools[1:])])  # labels never touch
    return [(j - (len(tools) - 1) / 2) * pitch for j in range(len(tools))]

def tool(name, label, glyph, planned, x):
    """One icon (shipped solid, planned outlined) or a two-letter badge, with its label."""
    paint = 'fill="none" stroke="{muted}"' if planned else 'fill="{text}"'
    if glyph in ICONS:
        mark = f'<use href="#i-{glyph}" x="{x:g}" {paint}/>'
    else:
        mark = (f'<rect x="{x-10:g}" y="-10" width="20" height="20" rx="5" {paint}/>'
                f'<text x="{x:g}" y="4" fill="{{{"muted" if planned else "bg"}}}" font-size="10" font-weight="700">{glyph}</text>')
    title = f'{name} (planned)' if planned else name
    return f'<g><title>{title}</title>{mark}<text x="{x:g}" y="24">{label}</text></g>'

def slots():
    """Each row with its turn k among the n rows that share its centre."""
    for cap, c, tools in ROWS:
        peers = [r[0] for r in ROWS if r[1] == c]
        yield cap, c, tools, peers.index(cap), len(peers)

def tools_text():
    """The alt sentence for the tool rows, in the README and docs index too."""
    def clause(caption, tools):
        shipped = [t[0] for t in tools if t[3]]
        planned = [t[0] for t in tools if not t[3]]
        parts = ([', '.join(shipped)] if shipped else []) + (['planned ' + ', '.join(planned)] if planned else [])
        return f'{caption}: {"; ".join(parts)}.'
    return 'Tools, outlined when planned. ' + ' '.join(clause(c, t) for c, _, t in ROWS)

def moving(cap, c, tools, k, n):
    """A row that takes its turn k of n over the cycle, an accent highlight stepping across its tools."""
    t0, t1, xx = k*T/n, (k+1)*T/n, xs(tools)
    turn = window([t0, t0 + 0.4, t1 - 0.4, t1], ['0', '1', '1', '0'], 0.4) if n > 1 else ''
    steps = window([t0 + j*(t1-t0)/len(tools) for j in range(len(tools))], [f'{x-26:g}' for x in xx], 0.4, attr='x', calc='discrete')
    return (f'<g transform="translate({c[0]} {c[1]})">{turn}'
            f'<rect x="{xx[0]-26:g}" y="-15" width="52" height="45" rx="10" fill="{{accent}}" opacity="0.2">{steps}</rect>'
            f'{row(cap, tools)}</g>')

def row(caption, tools):
    """Caption and icons centred on the local origin."""
    return (f'<text y="-21" font-size="13">{caption}</text>'
            + ''.join(tool(name, label, glyph, not proof, x) for (name, label, glyph, proof, _), x in zip(tools, xs(tools))))

O = (600, 432)          # owner
OW = 128
K, KW = (266, 463), 124  # calibrate station on the memory path, just before Plan
PH, PW = (545, 362), 96  # phone, above the owner
links = {   # owner touchpoints: path, label, label position
    'gate':   (f'M {O[0]-OW/2:g} {O[1]} C 450 {O[1]+4}, 330 {P[1]+22}, {P[0]+60} {P[1]+26}', 'morning gate', (392, 452)),
    'review': (f'M {O[0]+20} {O[1]-24} C 640 330, {R[0]} 300, {R[0]} {R[1]+28}', 'decision', (756, 318)),
    'merge':  (f'M {O[0]+OW/2:g} {O[1]-8} C 830 {O[1]-12}, 960 410, {OC[0]-14} {OC[1]+33}', 'merge', (872, 440)),
    'close':  (f'M {O[0]+30} {O[1]+24} C 680 500, 820 {CL[1]+6}, {CL[0]-68} {CL[1]+6}', 'draft to send', (760, 520)),
    'interview': (f'M {O[0]-OW/2+14:g} {O[1]+20} C 470 480, 380 {K[1]}, {K[0]+KW/2:g} {K[1]}', 'interview', (430, 494)),
    'dm':     (f'M {PH[0]+PW/2:g} {PH[1]-6} C 640 300, 690 270, 700 {R[1]+28}', 'DM', (628, 300)),
}

ROWFONT = FONT + ' fill="{muted}" stroke-width="1" font-size="12" text-anchor="middle"'

def svg(p):
    ring = '<rect class="ring" x="22" y="22" width="1156" height="576" rx="22" fill="none" stroke="{accent}" stroke-width="1.5" stroke-dasharray="2 7"/>'
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 620" role="img" aria-labelledby="title desc">',
        '<title id="title">WUWEI day loop</title>',
        '<desc id="desc">The WUWEI day is a loop. Plan, the owner\'s morning gate, leads to Build, where each item is built and checked until its checks pass. '
        'Review fans out to architecture, quality and security gates; a FIX verdict sends the item back to Build for one fix round and a delta check. '
        'A shepherd moves each pull request through CI, review threads and rebases until it merges, then Close runs the retro. '
        'Memory folds the learnings back into charters and notes so tomorrow\'s Plan starts from them. A sweep adds new work during the day. '
        'The owner is touched only at the morning gate, decisions, drafts to send and merges. Guards act at action time around every step. '
        'Before the first plan, Calibrate profiles the repositories and an owner interview turns preferences into configuration. '
        'Each item\'s review tier picks one gate or three. The owner can answer a decision from the phone through the Slack DM. '
        'A heartbeat on the guard ring proves the guards still behave. ' + tools_text() + '</desc>',
        '<style><![CDATA[',
        '.flow{stroke-dasharray:2 14;animation:flow 2.4s linear infinite}',
        '.slow{animation-duration:4s}',
        '@keyframes flow{to{stroke-dashoffset:-32}}',
        '.ring{animation:breathe 9s ease-in-out infinite}',
        '@keyframes breathe{0%,100%{opacity:.35}50%{opacity:.8}}',
        '.beat{animation:beat 6s ease-out infinite}',
        '@keyframes beat{0%,12%,100%{opacity:0}2%,7%{opacity:.9}4.5%{opacity:.1}}',
        '.still{display:none}',
        '@media (prefers-reduced-motion:reduce){.tok,.pulse,.beat,.tools{display:none}.flow,.ring{animation:none}.still{display:inline}}',
        ']]></style>',
        '<defs>',
        *[f'<path id="i-{k}" transform="translate(-10 -10) scale(.8333)" d="{d}"/>' for k, d in ICONS.items()],
        '<radialGradient id="halo" cx="50%" cy="58%" r="60%"><stop offset="0" stop-color="{accent}" stop-opacity="0.10"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>',
        '<radialGradient id="glow"><stop offset="0" stop-color="{accent}" stop-opacity="0.6"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>',
        '<marker id="ha" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L8 5L1 9" fill="none" stroke="{accent}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></marker>',
        '<marker id="hc" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L8 5L1 9" fill="none" stroke="{coral}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></marker>',
        '<g id="shield"><path d="M0 -9L7.5 -6V0.5C7.5 5 4.2 8 0 10C-4.2 8 -7.5 5 -7.5 0.5V-6Z" fill="{bg}" stroke="{accent}" stroke-width="1.6"/>'
        '<path d="M-3.2 0.4L-0.8 2.8L3.4 -1.8" fill="none" stroke="{accent}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></g>',
        '</defs>',
        '<rect width="1200" height="620" rx="28" fill="{bg}"/>',
        '<rect width="1200" height="620" rx="28" fill="url(#halo)"/>',
        ring,
        '<rect class="beat" x="22" y="22" width="1156" height="576" rx="22" fill="none" stroke="{accent}" stroke-width="2.5" opacity="0"/>',
        # guard ring label, cut into the ring
        '<rect x="930" y="12" width="232" height="22" fill="{bg}"/>',
        shield(952, 23),
        f'<text x="970" y="29" fill="{{muted}}" {FONT} font-size="16">Guards at action time</text>',
        '<rect x="48" y="587" width="96" height="22" fill="{bg}"/>',
        f'<text x="58" y="604" fill="{{muted}}" {FONT} font-size="16">heartbeat</text>',
        # title
        f'<text x="56" y="80" fill="{{text}}" {FONT} font-size="40" font-weight="700">无为 <tspan fill="{{atext}}">WUWEI</tspan></text>',
        f'<text x="57" y="112" fill="{{muted}}" {FONT} font-size="18">A chartered team of agents, one calm day</text>',
        # owner links (under everything else)
        '<g fill="none" stroke="{warm}" stroke-width="1.6" stroke-dasharray="3 6" opacity="0.8">',
        *[f'<path d="{d}"/>' for d, _, _ in links.values()],
        '</g>',
        # edges
        '<g fill="none" stroke-linecap="round">',
        f'<path d="{path(seg_mem)}" stroke="{{accent}}" stroke-opacity="0.28" stroke-width="3"/>',
        f'<path d="{path(seg_pb, seg_br, seg_rj, seg_jo, seg_ohalf, seg_oc)}" stroke="{{accent}}" stroke-opacity="0.35" stroke-width="3.5"/>',
        f'<path d="{path(lane_top)}" stroke="{{accent}}" stroke-opacity="0.35" stroke-width="2"/>',
        f'<path d="{path(lane_bot)}" stroke="{{accent}}" stroke-opacity="0.35" stroke-width="2"/>',
        f'<circle cx="{OC[0]}" cy="{OC[1]}" r="{OR}" stroke="{{accent}}" stroke-opacity="0.35" stroke-width="2"/>',
        f'<circle cx="{KC[0]}" cy="{KC[1]}" r="{KR}" stroke="{{accent}}" stroke-opacity="0.35" stroke-width="2"/>',
        f'<path d="M {f(B)} L {f(KT)}" stroke="{{accent}}" stroke-opacity="0.35" stroke-width="2"/>',
        f'<path d="{path(seg_sweep)}" stroke="{{accent}}" stroke-opacity="0.35" stroke-width="2"/>',
        f'<path d="{path(fix_a, fix_b, fix_c)}" stroke="{{coral}}" stroke-opacity="0.45" stroke-width="2"/>',
        # flowing dashes
        f'<path d="{arrow_mem}" stroke="{{accent}}" stroke-opacity="0" stroke-width="3" marker-end="url(#ha)"/>',
        f'<path d="{arrow_close}" stroke="{{accent}}" stroke-opacity="0" stroke-width="3" marker-end="url(#ha)"/>',
        f'<path class="flow slow" d="{path(seg_mem)}" stroke="{{accent}}" stroke-width="3"/>',
        f'<path class="flow" d="{path(seg_pb, seg_br, seg_rj, seg_jo, seg_ohalf, seg_oc)}" stroke="{{accent}}" stroke-width="3.5"/>',
        f'<path class="flow" d="{path(lane_top)}" stroke="{{accent}}" stroke-width="2.5"/>',
        f'<path class="flow" d="{path(lane_bot)}" stroke="{{accent}}" stroke-width="2.5"/>',
        f'<path class="flow" d="M {f(OT)} {seg_ofull.d}" stroke="{{accent}}" stroke-width="2.5"/>',
        f'<path class="flow" d="M {f(KT)} A {KR} {KR} 0 0 1 {f(KB)} A {KR} {KR} 0 0 1 {f(KT)}" stroke="{{accent}}" stroke-width="2.5"/>',
        f'<path class="flow" d="{path(seg_sweep)}" stroke="{{accent}}" stroke-width="2.5" marker-end="url(#ha)"/>',
        f'<path class="flow" d="{path(fix_a, fix_b, fix_c)}" stroke="{{coral}}" stroke-width="2.5" marker-end="url(#hc)"/>',
        '</g>',
        # owner pulses
        pulse(links['gate'][0], A_, A_.events['gate']),
        pulse(links['close'][0], A_, A_.events['close']),
        pulse(links['review'][0], B_, B_.events['review']),
        pulse(links['merge'][0], D_, D_.events['merge']),
        pulse(links['interview'][0], MEM, MEM.t * 0.8),
        pulse(links['dm'][0], B_, B_.events['review'] + 1.2),
        # tokens, under the nodes so they pass behind them
        token(MEM).replace('r="7"', 'r="5"'),
        token(A_), token(B_), ghost(lane_top, B_, b_rj0, b_rj1), ghost(lane_bot, B_, b_rj0, b_rj1),
        token(C_, window([c_fix0 - 0.1, c_fix0 + 0.4, c_fix1 - 0.4, c_fix1], ['{accent}', '{coral}', '{coral}', '{accent}'], C_.start, attr='stroke')),
        token(D_),
        # gate markers and labels
        f'<g fill="{{panel}}" stroke="{{accent}}" stroke-width="2">'
        + ''.join(f'<circle cx="{GX}" cy="{R[1]+dy}" r="8"/>' for dy in (-LANE, 0, LANE)) + '</g>',
        f'<g fill="{{muted}}" {FONT} font-size="16" text-anchor="middle">'
        f'<text x="{GX}" y="{R[1]-LANE-16}">architecture</text><text x="{GX}" y="{R[1]-16}">quality</text>'
        f'<text x="{GX}" y="{R[1]+LANE-16}">security</text><text x="{GX+20}" y="{R[1]+LANE+30}">tier: one gate or three</text></g>',
        # main nodes
        f'<g {FONT} font-size="24" font-weight="600" text-anchor="middle">',
        *[f'<g><rect x="{c[0]-w/2:g}" y="{c[1]-25}" width="{w}" height="56" rx="18" fill="{{shadow}}" opacity="0.22"/>'
          f'<rect x="{c[0]-w/2:g}" y="{c[1]-28}" width="{w}" height="56" rx="18" fill="{{panel}}" stroke="{{accent}}" stroke-width="2"/>'
          f'<text x="{c[0]}" y="{c[1]+8}" fill="{{text}}">{t}</text></g>'
          for c, w, t in ((P, 136, 'Plan'), (B, 136, 'Build'), (R, 150, 'Review'), (CL, 136, 'Close'))],
        '</g>',
        shield(B[0]+64, B[1]-28), shield(R[0]+71, R[1]-28), shield(OC[0]+26, OC[1]-26), shield(CL[0]+64, CL[1]-28),
        # owner node
        f'<rect x="{O[0]-OW/2:g}" y="{O[1]-21}" width="{OW}" height="48" rx="24" fill="{{shadow}}" opacity="0.22"/>',
        f'<rect x="{O[0]-OW/2:g}" y="{O[1]-24}" width="{OW}" height="48" rx="24" fill="{{panel}}" stroke="{{warm}}" stroke-width="2"/>',
        f'<text x="{O[0]}" y="{O[1]+7}" fill="{{warm}}" {FONT} font-size="20" font-weight="600" text-anchor="middle">Owner</text>',
        # calibrate station and phone
        f'<rect x="{K[0]-KW/2:g}" y="{K[1]-20}" width="{KW}" height="40" rx="20" fill="{{panel}}" stroke="{{accent}}" stroke-width="2"/>',
        f'<text x="{K[0]}" y="{K[1]+6}" fill="{{text}}" {FONT} font-size="18" font-weight="600" text-anchor="middle">Calibrate</text>',
        f'<path d="M {PH[0]+15} {PH[1]+18} L {PH[0]+25} {O[1]-24}" fill="none" stroke="{{warm}}" stroke-width="1.6" stroke-dasharray="3 6" opacity="0.8"/>',
        f'<rect x="{PH[0]-PW/2:g}" y="{PH[1]-18}" width="{PW}" height="36" rx="18" fill="{{panel}}" stroke="{{warm}}" stroke-width="2"/>',
        f'<text x="{PH[0]}" y="{PH[1]+6}" fill="{{warm}}" {FONT} font-size="17" font-weight="600" text-anchor="middle">Phone</text>',
        # captions
        f'<g fill="{{muted}}" {FONT} font-size="16">',
        f'<text x="{KC[0]}" y="{KC[1]+6}" text-anchor="middle">check</text>',
        f'<text x="{KC[0]+KR+12}" y="{KC[1]+6}">test first</text>',
        f'<text x="{OC[0]}" y="{OC[1]+6}" text-anchor="middle">PR</text>',
        f'<text x="{OC[0]-OR-14}" y="{OC[1]+2}" text-anchor="end">shepherd</text>',
        f'<text x="{OC[0]-OR-14}" y="{OC[1]+22}" text-anchor="end">CI, threads, rebase</text>',
        f'<text x="{SW0[0]-12}" y="{SW0[1]+6}" text-anchor="end">sweep: new work</text>',
        '</g>',
        f'<text x="742" y="84" fill="{{coral}}" {FONT} font-size="16" text-anchor="middle">FIX: one fix round, then a delta check</text>',
        f'<text x="585" y="584" fill="{{atext}}" {FONT} font-size="18" font-weight="600" text-anchor="middle">Memory across days</text>',
        f'<g fill="{{warm}}" {FONT} font-size="16" text-anchor="middle">'
        + ''.join(f'<text x="{x}" y="{y}">{t}</text>' for _, t, (x, y) in links.values()) + '</g>',
        # tools per station: animated rows, and a still copy for reduced motion
        f'<g class="tools" {ROWFONT}>',
        *[moving(*s) for s in slots()],
        '</g>',
        f'<g class="still" {ROWFONT}>',
        *[f'<g transform="translate({c[0]} {c[1] + 48 * (k - (n - 1) / 2):g}) scale({0.8 if n > 1 else 1})">{row(cap, tools)}</g>'
          for cap, c, tools, k, n in slots()],
        '</g>',
        '</svg>',
    ]
    out = '\n'.join(parts) + '\n'
    for k, v in p.items():
        out = out.replace('{' + k + '}', v)
    return out

if __name__ == '__main__':
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    for name, pal in PAL.items():
        (root / f'docs/site/assets/hero-{name}.svg').write_text(svg(pal))
