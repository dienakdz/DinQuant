import './index.less'

import { Icon, Menu, Dropdown } from 'ant-design-vue'
import { i18nRender } from '@/locales'
import i18nMixin from '@/store/i18n-mixin'

const locales = ['en-US', 'ja-JP', 'ko-KR', 'vi-VN', 'th-TH', 'ar-SA', 'fr-FR', 'de-DE', 'zh-TW', 'zh-CN']
const languageLabels = {
  'zh-CN': 'Simplified Chinese',
  'zh-TW': 'Traditional Chinese',
  'en-US': 'English',
  'ja-JP': 'Japanese',
  'ko-KR': '한국어',
  'vi-VN': 'Tiếng Việt',
  'th-TH': 'ไทย',
  'ar-SA': 'العربية',
  'fr-FR': 'Français',
  'de-DE': 'Deutsch'
}
// eslint-disable-next-line
const languageIcons = {
  'zh-CN': '🇨🇳',
  'zh-TW': 'sg',
  'en-US': '🇺🇸',
  'ja-JP': '🇯🇵',
  'ko-KR': '🇰🇷',
  'vi-VN': '🇻🇳',
  'th-TH': '🇹🇭',
  'ar-SA': '🇸🇦',
  'fr-FR': '🇫🇷',
  'de-DE': '🇩🇪'
}

const SelectLang = {
  props: {
    prefixCls: {
      type: String,
      default: 'ant-pro-drop-down'
    }
  },
  name: 'SelectLang',
  mixins: [i18nMixin],
  render () {
    const { prefixCls } = this
    const changeLang = ({ key }) => {
      this.setLang(key)
    }
    const langMenu = (
      <Menu class={['menu', 'ant-pro-header-menu']} selectedKeys={[this.currentLang]} onClick={changeLang}>
        {locales.map(locale => (
          <Menu.Item key={locale}>
            <span role="img" aria-label={languageLabels[locale]}>
              {languageIcons[locale]}
            </span>{' '}
            {languageLabels[locale]}
          </Menu.Item>
        ))}
      </Menu>
    )
    return (
      <Dropdown overlay={langMenu} placement="bottomRight">
        <span class={prefixCls}>
          <Icon type="global" title={i18nRender('navBar.lang')} />
        </span>
      </Dropdown>
    )
  }
}

export default SelectLang
